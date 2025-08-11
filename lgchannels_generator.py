#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import json
import os
import gzip
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
import logging
import time
import sys

# --- Configuration ---
BASE_URL = "https://us.lgchannels.com"
API_BASE_URL = f"{BASE_URL}/api/v1"
DEFAULT_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Host': 'us.lgchannels.com',
    'Origin': 'https://lgchannels.com',
    'Referer': 'https://lgchannels.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0'
}

# --- Output Settings ---
OUTPUT_DIR = "lgchannels_playlist"
PLAYLIST_FILENAME = "lgchannels.m3u"
EPG_FILENAME = "lgchannels_epg.xml.gz"
REQUEST_TIMEOUT = 30
EPG_HOURS = 24  # Number of hours of EPG data to fetch

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s',
    stream=sys.stdout
)

def ensure_output_dir():
    """Ensure the output directory exists."""
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            logging.info(f"Created output directory: {OUTPUT_DIR}")
        except OSError as e:
            logging.error(f"Failed to create directory {OUTPUT_DIR}: {e}")
            raise

def fetch_data(url, params=None, headers=None, retries=2):
    """Fetch data from the API with error handling and retries."""
    if headers is None:
        headers = DEFAULT_HEADERS
    
    for attempt in range(retries + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == retries:
                logging.error(f"Failed to fetch {url} after {retries + 1} attempts: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logging.error(f"Response content: {e.response.text[:500]}")
                return None
            time.sleep(1 * (attempt + 1))
    return None

def get_channels():
    """Fetch the list of channels from LG Channels API."""
    logging.info("Fetching channel list...")
    
    # First, get the channel lineup
    lineup_url = f"{API_BASE_URL}/lineup"
    data = fetch_data(lineup_url)
    
    if not data or 'channels' not in data:
        logging.error("Failed to fetch or parse channel list")
        return []
    
    channels = []
    for channel in data['channels']:
        try:
            channel_info = {
                'id': channel.get('channelId'),
                'name': channel.get('name', 'Unknown'),
                'number': channel.get('channelNumber', '0'),
                'logo': channel.get('logoUrl', ''),
                'stream_url': channel.get('streamUrl', ''),
                'description': channel.get('description', ''),
                'categories': channel.get('categories', [])
            }
            
            # If stream URL is relative, make it absolute
            if channel_info['stream_url'] and not channel_info['stream_url'].startswith('http'):
                channel_info['stream_url'] = f"{BASE_URL}{channel_info['stream_url']}"
                
            # If logo URL is relative, make it absolute
            if channel_info['logo'] and not channel_info['logo'].startswith('http'):
                channel_info['logo'] = f"{BASE_URL}{channel_info['logo']}"
            
            channels.append(channel_info)
        except Exception as e:
            logging.warning(f"Error processing channel {channel.get('channelId')}: {e}")
    
    logging.info(f"Found {len(channels)} channels")
    return channels

def get_epg_data(channel_id, hours=EPG_HOURS):
    """Fetch EPG data for a specific channel."""
    end_time = datetime.utcnow() + timedelta(hours=hours)
    start_time = datetime.utcnow()
    
    params = {
        'channelId': channel_id,
        'startTime': start_time.isoformat() + 'Z',
        'endTime': end_time.isoformat() + 'Z',
        'limit': 100  # Adjust based on API limits
    }
    
    epg_url = f"{API_BASE_URL}/epg"
    data = fetch_data(epg_url, params=params)
    
    if not data or 'programs' not in data:
        logging.warning(f"No EPG data found for channel {channel_id}")
        return []
    
    return data['programs']

def generate_m3u_playlist(channels):
    """Generate M3U playlist file from channel list."""
    m3u_content = "#EXTM3U x-tvg-url=" + EPG_FILENAME + "\n"
    
    for channel in channels:
        if not channel.get('stream_url'):
            continue
            
        m3u_content += f"#EXTINF:-1 tvg-id=\"{channel['id']}\" "
        m3u_content += f"tvg-name=\"{channel['name']}\" "
        m3u_content += f"tvg-logo=\"{channel['logo']}\" "
        m3u_content += f"group-title=\"{','.join(channel.get('categories', []))}\","
        m3u_content += f"{channel['name']}\n"
        m3u_content += f"{channel['stream_url']}\n"
    
    return m3u_content

def generate_epg_xml(channels):
    """Generate XMLTV EPG data."""
    tv = ET.Element('tv', {'generator-info-name': 'LG Channels EPG Generator', 'generator-info-url': 'https://github.com/yourusername/lgchannels-epg'})
    
    # Add channel information
    for channel in channels:
        channel_elem = ET.SubElement(tv, 'channel', {'id': str(channel['id'])})
        ET.SubElement(channel_elem, 'display-name').text = channel['name']
        if channel.get('logo'):
            ET.SubElement(channel_elem, 'icon', {'src': channel['logo']})
    
    # Add programs
    for channel in channels:
        programs = get_epg_data(channel['id'])
        for program in programs:
            try:
                program_elem = ET.SubElement(tv, 'programme', {
                    'channel': str(channel['id']),
                    'start': format_time(program.get('startTime')),
                    'stop': format_time(program.get('endTime'))
                })
                
                ET.SubElement(program_elem, 'title').text = program.get('title', 'Unknown')
                
                if 'description' in program:
                    ET.SubElement(program_elem, 'desc').text = program['description']
                
                if 'genre' in program:
                    genre = program['genre']
                    if isinstance(genre, list):
                        for g in genre:
                            ET.SubElement(program_elem, 'category').text = g
                    else:
                        ET.SubElement(program_elem, 'category').text = genre
            except Exception as e:
                logging.warning(f"Error processing program for channel {channel['id']}: {e}")
    
    return ET.ElementTree(tv)

def format_time(time_str):
    """Format time string to XMLTV format."""
    if not time_str:
        return ""
    try:
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return dt.strftime('%Y%m%d%H%M%S %z')
    except (ValueError, AttributeError) as e:
        logging.warning(f"Error formatting time '{time_str}': {e}")
        return ""

def save_gzipped_xml(tree, filepath):
    """Save XML tree to a gzipped file."""
    try:
        # Create XML declaration and DOCTYPE
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        # Add DOCTYPE declaration
        doctype = '<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
        # Convert the XML tree to a string
        xml_string = ET.tostring(tree.getroot(), encoding='unicode', method='xml')
        
        # Combine everything
        full_xml = xml_declaration + doctype + xml_string
        
        # Write to gzipped file
        with gzip.open(filepath, 'wb') as f:
            f.write(full_xml.encode('utf-8'))
        
        logging.info(f"EPG XML saved to {filepath}")
    except Exception as e:
        logging.error(f"Error saving gzipped XML: {e}")

def main():
    """Main function to generate M3U and EPG files."""
    ensure_output_dir()
    
    # Get channels
    channels = get_channels()
    if not channels:
        logging.error("No channels found. Exiting.")
        return
    
    # Generate M3U playlist
    m3u_content = generate_m3u_playlist(channels)
    m3u_path = os.path.join(OUTPUT_DIR, PLAYLIST_FILENAME)
    try:
        with open(m3u_path, 'w', encoding='utf-8') as f:
            f.write(m3u_content)
        logging.info(f"M3U playlist saved to {m3u_path}")
    except Exception as e:
        logging.error(f"Error saving M3U playlist: {e}")
    
    # Generate EPG
    epg_tree = generate_epg_xml(channels)
    epg_path = os.path.join(OUTPUT_DIR, EPG_FILENAME)
    save_gzipped_xml(epg_tree, epg_path)

if __name__ == "__main__":
    logging.info("Starting LG Channels M3U/EPG Generator")
    main()
    logging.info("Generation complete")

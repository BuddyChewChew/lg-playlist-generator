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
import re
import sys
import math
from urllib.parse import urljoin

# --- Configuration ---
BASE_URL = "https://api.lgchannels.com"
DEFAULT_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Host': 'api.lgchannels.com',
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
EPG_DAYS = 3  # Number of days of EPG data to fetch

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
                return None
            time.sleep(1 * (attempt + 1))  # Exponential backoff
    return None

def get_channels():
    """Fetch the list of channels from LG Channels API."""
    logging.info("Fetching channel list...")
    url = f"{BASE_URL}/v1/channels"
    data = fetch_data(url)
    
    if not data or 'channels' not in data:
        logging.error("Failed to fetch or parse channel list")
        return []
    
    channels = []
    for channel in data['channels']:
        try:
            channel_info = {
                'id': channel.get('id'),
                'name': channel.get('name', 'Unknown'),
                'number': channel.get('channelNumber', '0'),
                'logo': channel.get('logoUrl', ''),
                'stream_url': channel.get('streamUrl', ''),
                'description': channel.get('description', ''),
                'categories': channel.get('categories', [])
            }
            channels.append(channel_info)
        except Exception as e:
            logging.warning(f"Error processing channel {channel.get('id')}: {e}")
    
    logging.info(f"Found {len(channels)} channels")
    return channels

def get_epg_data(channel_id, days=EPG_DAYS):
    """Fetch EPG data for a specific channel."""
    end_time = datetime.utcnow() + timedelta(days=days)
    start_time = datetime.utcnow()
    
    params = {
        'channelId': channel_id,
        'startTime': start_time.isoformat() + 'Z',
        'endTime': end_time.isoformat() + 'Z'
    }
    
    url = f"{BASE_URL}/v1/epg"
    data = fetch_data(url, params=params)
    
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
    tv = ET.Element('tv')
    
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
    
    return ET.ElementTree(tv)

def format_time(time_str):
    """Format time string to XMLTV format."""
    if not time_str:
        return ""
    try:
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        return dt.strftime('%Y%m%d%H%M%S %z')
    except (ValueError, AttributeError):
        return ""

def save_gzipped_xml(tree, filepath):
    """Save XML tree to a gzipped file."""
    try:
        xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n'
        # Add DOCTYPE declaration
        xml_string += '<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
        # Convert the XML tree to a string and append it
        xml_string += ET.tostring(tree.getroot(), encoding='unicode', method='xml')
        
        # Write to gzipped file
        with gzip.open(filepath, 'wb') as f:
            f.write(xml_string.encode('utf-8'))
        
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

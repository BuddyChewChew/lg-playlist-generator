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
from urllib.parse import urljoin

# --- Configuration ---
BASE_URL = "https://channel-lineup.lgchannels.com"
CHANNELS_ENDPOINT = f"{BASE_URL}/api/channels"
EPG_ENDPOINT = f"{BASE_URL}/api/epg"

DEFAULT_HEADERS = {
    'Accept': 'application/json, text/plain, */*',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
    'Host': 'channel-lineup.lgchannels.com',
    'Origin': 'https://lgchannels.com',
    'Referer': 'https://lgchannels.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-site',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0',
    'X-Requested-With': 'XMLHttpRequest'
}

# --- Output Settings ---
OUTPUT_DIR = "lgchannels_playlist"
PLAYLIST_FILENAME = "lgchannels.m3u"
EPG_FILENAME = "lgchannels_epg.xml.gz"
REQUEST_TIMEOUT = 30
EPG_HOURS = 24  # Number of hours of EPG data to fetch
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(funcName)s] %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

def ensure_output_dir():
    """Ensure the output directory exists."""
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            logger.info(f"Created output directory: {OUTPUT_DIR}")
            return True
        except OSError as e:
            logger.error(f"Failed to create directory {OUTPUT_DIR}: {e}")
            return False
    return True

def fetch_data(url, params=None, headers=None, retries=MAX_RETRIES):
    """Fetch data from the API with error handling and retries."""
    if headers is None:
        headers = DEFAULT_HEADERS
    
    for attempt in range(retries + 1):
        try:
            logger.debug(f"Fetching {url} (attempt {attempt + 1}/{retries + 1})")
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
                logger.error(f"Failed to fetch {url} after {retries + 1} attempts: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    logger.error(f"Response status: {e.response.status_code}")
                    logger.error(f"Response content: {e.response.text[:500]}")
                return None
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {RETRY_DELAY} seconds...")
            time.sleep(RETRY_DELAY * (attempt + 1))
    return None

def get_channels():
    """Fetch the list of channels from LG Channels API."""
    logger.info("Fetching channel list...")
    
    data = fetch_data(CHANNELS_ENDPOINT)
    
    if not data or not isinstance(data, list):
        logger.error("Failed to fetch or parse channel list")
        return []
    
    channels = []
    for channel in data:
        try:
            if not isinstance(channel, dict):
                logger.warning(f"Skipping invalid channel data: {channel}")
                continue
                
            channel_id = channel.get('id')
            if not channel_id:
                logger.warning("Skipping channel with missing ID")
                continue
                
            stream_url = channel.get('streamUrl', '')
            if not stream_url or not stream_url.startswith('http'):
                stream_url = urljoin(BASE_URL, stream_url)
                
            logo_url = channel.get('logoUrl', '')
            if logo_url and not logo_url.startswith('http'):
                logo_url = urljoin(BASE_URL, logo_url)
            
            channel_info = {
                'id': channel_id,
                'name': channel.get('name', f'Channel {channel_id}'),
                'number': channel.get('channelNumber', '0'),
                'logo': logo_url,
                'stream_url': stream_url,
                'description': channel.get('description', ''),
                'categories': channel.get('categories', [])
            }
            
            channels.append(channel_info)
            logger.debug(f"Added channel: {channel_info['name']} (ID: {channel_id})")
            
        except Exception as e:
            logger.error(f"Error processing channel data: {e}\nChannel data: {channel}")
    
    logger.info(f"Successfully processed {len(channels)} channels")
    return channels

def get_epg_data(channel_id, hours=EPG_HOURS):
    """Fetch EPG data for a specific channel."""
    if not channel_id:
        logger.warning("No channel ID provided for EPG data")
        return []
        
    end_time = datetime.utcnow() + timedelta(hours=hours)
    start_time = datetime.utcnow()
    
    epg_url = f"{EPG_ENDPOINT}/{channel_id}"
    params = {
        'startTime': start_time.isoformat() + 'Z',
        'endTime': end_time.isoformat() + 'Z'
    }
    
    logger.debug(f"Fetching EPG for channel {channel_id}...")
    data = fetch_data(epg_url, params=params)
    
    if not data or not isinstance(data, dict) or 'programs' not in data:
        logger.warning(f"No EPG data found for channel {channel_id}")
        return []
    
    programs = data['programs']
    logger.debug(f"Found {len(programs)} programs for channel {channel_id}")
    return programs

def generate_m3u_playlist(channels):
    """Generate M3U playlist file from channel list."""
    if not channels:
        logger.error("No channels available to generate M3U playlist")
        return "#EXTM3U"
    
    m3u_content = ["#EXTM3U x-tvg-url=" + EPG_FILENAME]
    
    for channel in channels:
        if not channel.get('stream_url'):
            logger.warning(f"Skipping channel {channel.get('name')} - no stream URL")
            continue
            
        extinf = f"#EXTINF:-1 tvg-id=\"{channel['id']}\" "
        extinf += f"tvg-name=\"{channel['name']}\" "
        
        if channel.get('logo'):
            extinf += f"tvg-logo=\"{channel['logo']}\" "
            
        if channel.get('categories'):
            categories = [c for c in channel['categories'] if c]
            if categories:
                extinf += f"group-title=\"{','.join(categories)}\" "
        
        extinf += f",{channel['name']}"
        
        m3u_content.extend([extinf, channel['stream_url']])
    
    return '\n'.join(m3u_content) + '\n'

def generate_epg_xml(channels):
    """Generate XMLTV EPG data."""
    if not channels:
        logger.error("No channels available to generate EPG")
        return None
        
    tv_attrs = {
        'generator-info-name': 'LG Channels EPG Generator',
        'generator-info-url': 'https://github.com/yourusername/lgchannels-epg',
        'source-info-name': 'LG Channels',
        'source-info-url': 'https://lgchannels.com/'
    }
    
    tv = ET.Element('tv', {k: str(v) for k, v in tv_attrs.items() if v})
    
    # Add channel information
    for channel in channels:
        try:
            channel_id = channel.get('id')
            if not channel_id:
                logger.warning("Skipping channel with missing ID")
                continue
                
            channel_elem = ET.SubElement(tv, 'channel', {'id': str(channel_id)})
            ET.SubElement(channel_elem, 'display-name').text = channel.get('name', f'Channel {channel_id}')
            
            if channel.get('logo'):
                ET.SubElement(channel_elem, 'icon', {'src': channel['logo']})
                
            if channel.get('description'):
                ET.SubElement(channel_elem, 'desc').text = channel['description']
                
            logger.debug(f"Added channel to EPG: {channel.get('name')} (ID: {channel_id})")
            
        except Exception as e:
            logger.error(f"Error adding channel {channel.get('id')} to EPG: {e}")
    
    # Add programs
    for channel in channels:
        channel_id = channel.get('id')
        if not channel_id:
            continue
            
        try:
            programs = get_epg_data(channel_id)
            if not programs:
                continue
                
            for program in programs:
                try:
                    if not isinstance(program, dict):
                        continue
                        
                    start_time = program.get('startTime')
                    end_time = program.get('endTime')
                    
                    if not start_time or not end_time:
                        continue
                        
                    program_attrs = {
                        'channel': str(channel_id),
                        'start': format_time(start_time),
                        'stop': format_time(end_time)
                    }
                    
                    program_elem = ET.SubElement(tv, 'programme', program_attrs)
                    
                    # Add program title
                    title = program.get('title')
                    if title:
                        ET.SubElement(program_elem, 'title').text = title
                    
                    # Add program description
                    desc = program.get('description')
                    if desc:
                        ET.SubElement(program_elem, 'desc').text = desc
                    
                    # Add program categories
                    genre = program.get('genre')
                    if genre:
                        if isinstance(genre, list):
                            for g in genre:
                                if g:
                                    ET.SubElement(program_elem, 'category').text = g
                        elif genre:
                            ET.SubElement(program_elem, 'category').text = genre
                    
                    # Add program image if available
                    image_url = program.get('imageUrl')
                    if image_url and not image_url.startswith('http'):
                        image_url = urljoin(BASE_URL, image_url)
                        
                    if image_url:
                        ET.SubElement(program_elem, 'icon', {'src': image_url})
                    
                except Exception as e:
                    logger.error(f"Error processing program for channel {channel_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error getting EPG for channel {channel_id}: {e}")
    
    return ET.ElementTree(tv)

def format_time(time_str):
    """Format time string to XMLTV format."""
    if not time_str:
        return ""
        
    try:
        # Handle different time formats
        if 'Z' in time_str:
            time_str = time_str.replace('Z', '+00:00')
            
        if '.' in time_str:  # Handle fractional seconds
            time_str = time_str.split('.')[0] + time_str[time_str.find('.'):].replace(':', '')
            
        dt = datetime.fromisoformat(time_str)
        return dt.strftime('%Y%m%d%H%M%S %z')
    except (ValueError, AttributeError) as e:
        logger.warning(f"Error formatting time '{time_str}': {e}")
        return ""

def save_gzipped_xml(tree, filepath):
    """Save XML tree to a gzipped file."""
    if not tree:
        logger.error("No XML tree to save")
        return False
        
    try:
        # Create XML declaration and DOCTYPE
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        # Add DOCTYPE declaration
        doctype = '<!DOCTYPE tv SYSTEM "xmltv.dtd">\n'
        # Convert the XML tree to a string
        xml_string = ET.tostring(tree.getroot(), encoding='unicode', method='xml')
        
        # Combine everything
        full_xml = xml_declaration + doctype + xml_string
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        
        # Write to gzipped file
        with gzip.open(filepath, 'wb') as f:
            f.write(full_xml.encode('utf-8'))
        
        logger.info(f"EPG XML saved to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving gzipped XML to {filepath}: {e}")
        return False

def save_playlist(content, filepath):
    """Save M3U playlist to file."""
    if not content:
        logger.error("No content to save to playlist")
        return False
        
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"M3U playlist saved to {filepath}")
        return True
    except Exception as e:
        logger.error(f"Error saving M3U playlist to {filepath}: {e}")
        return False

def main():
    """Main function to generate M3U and EPG files."""
    start_time = time.time()
    logger.info("=== Starting LG Channels M3U/EPG Generator ===")
    
    # Ensure output directory exists
    if not ensure_output_dir():
        logger.error("Failed to create output directory. Exiting.")
        sys.exit(1)
    
    # Get channels
    channels = get_channels()
    if not channels:
        logger.error("No channels found. Exiting.")
        sys.exit(1)
    
    # Generate M3U playlist
    m3u_path = os.path.join(OUTPUT_DIR, PLAYLIST_FILENAME)
    m3u_content = generate_m3u_playlist(channels)
    if not save_playlist(m3u_content, m3u_path):
        logger.error("Failed to save M3U playlist")
    
    # Generate EPG
    epg_path = os.path.join(OUTPUT_DIR, EPG_FILENAME)
    epg_tree = generate_epg_xml(channels)
    if epg_tree and not save_gzipped_xml(epg_tree, epg_path):
        logger.error("Failed to save EPG XML")
    
    # Calculate and log execution time
    execution_time = time.time() - start_time
    logger.info(f"=== Generation completed in {execution_time:.2f} seconds ===")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}", exc_info=True)
        sys.exit(1)

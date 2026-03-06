import json
import requests
import datetime
import time
import os

# Configuration
API_URL = 'https://api.lgchannels.com/api/v1.0/schedulelist'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Updated Filenames
M3U_FILENAME = "lg_channels_us.m3u"
EPG_FILENAME = "lg_channels_us.xml"

# Replace 'YOUR_GITHUB_USERNAME' with your actual GitHub handle
GITHUB_USERNAME = "BuddyChewChew"
REPO_NAME = "lg"
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/main/{EPG_FILENAME}"

headers = {
    'user-agent': USER_AGENT,
    'x-device-country': 'US',
    'x-device-language': 'en',
}

def fetch_data():
    try:
        response = requests.get(API_URL, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def generate_files(data):
    if not data or 'categories' not in data:
        print("No valid data received from API.")
        return

    # Header with the EPG link pointing to lg_channels_us.xml
    m3u_lines = [f'#EXTM3U x-tvg-url="{GITHUB_RAW_URL}"']
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv>']

    processed_channels = set()

    for category in data.get('categories', []):
        cat_name = category.get('categoryName', 'General')
        
        for chan in category.get('channels', []):
            chan_id = chan.get('channelId', '')
            if not chan_id or chan_id in processed_channels:
                continue
            
            chan_name = chan.get('channelName', 'Unknown')
            # Clean stream URL
            stream_url = chan.get('mediaStaticUrl', '').split('?')[0]
            
            if not stream_url:
                continue

            # M3U Entry
            logo = ""
            if chan.get('programs'):
                logo = chan['programs'][0].get('imageUrl', '')

            m3u_lines.append(f'#EXTINF:-1 tvg-id="{chan_id}" tvg-name="{chan_name}" tvg-logo="{logo}" group-title="{cat_name}",{chan_name}')
            m3u_lines.append(stream_url)

            # XMLTV Channel Definition
            xml_lines.append(f'  <channel id="{chan_id}">\n    <display-name>{chan_name}</display-name>\n  </channel>')
            
            # XMLTV Program Listings
            for prog in chan.get('programs', []):
                # Format: YYYYMMDDHHMMSS +0000
                start = prog.get('startDateTime', '').replace('-', '').replace(':', '').replace('T', '').replace('Z', ' +0000')
                end = prog.get('endDateTime', '').replace('-', '').replace(':', '').replace('T', '').replace('Z', ' +0000')
                title = prog.get('programTitle', 'No Title').replace('&', '&amp;')
                desc = prog.get('description', '').replace('&', '&amp;')
                
                if start and end:
                    xml_lines.append(f'  <programme start="{start}" stop="{end}" channel="{chan_id}">')
                    xml_lines.append(f'    <title>{title}</title>')
                    xml_lines.append(f'    <desc>{desc}</desc>')
                    xml_lines.append('  </programme>')

            processed_channels.add(chan_id)

    xml_lines.append('</tv>')

    # Write M3U file
    with open(M3U_FILENAME, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))

    # Write EPG XML file
    with open(EPG_FILENAME, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))

    print(f"Files generated: {M3U_FILENAME}, {EPG_FILENAME}")

if __name__ == "__main__":
    raw_data = fetch_data()
    generate_files(raw_data)

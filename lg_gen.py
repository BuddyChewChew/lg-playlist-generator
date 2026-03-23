import json
import requests
import os

# Configuration
API_URL = 'https://api.lgchannels.com/api/v1.0/schedulelist'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

# Filenames (Removed playlists directory)
M3U_FILENAME = "lg_channels_mx.m3u"
EPG_FILENAME = "lg_channels_mx.xml"

# User and Repo Details
GITHUB_USERNAME = "BuddyChewChew"
REPO_NAME = "lg-playlist-generator"
# Corrected URL to point to root
GITHUB_RAW_URL = f"https://raw.githubusercontent.com/s-digweed/{REPO_NAME}/main/{EPG_FILENAME}"

headers = {
    'user-agent': USER_AGENT,
    'x-device-country': 'MX',
    'x-device-language': 'es',
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
        return

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
            stream_url = chan.get('mediaStaticUrl', '').split('?')[0]
            if not stream_url: continue

            logo = chan['programs'][0].get('imageUrl', '') if chan.get('programs') else ""
            m3u_lines.append(f'#EXTINF:-1 tvg-id="{chan_id}" tvg-name="{chan_name}" tvg-logo="{logo}" group-title="{cat_name}",{chan_name}')
            m3u_lines.append(stream_url)

            xml_lines.append(f'  <channel id="{chan_id}">\n    <display-name>{chan_name}</display-name>\n  </channel>')
            for prog in chan.get('programs', []):
                start = prog.get('startDateTime', '').replace('-', '').replace(':', '').replace('T', '').replace('Z', ' +0000')
                end = prog.get('endDateTime', '').replace('-', '').replace(':', '').replace('T', '').replace('Z', ' +0000')
                title = prog.get('programTitle', 'No Title').replace('&', '&amp;')
                desc = prog.get('description', '').replace('&', '&amp;')
                if start and end:
                    xml_lines.append(f'  <programme start="{start}" stop="{end}" channel="{chan_id}">')
                    xml_lines.append(f'    <title>{title}</title>\n    <desc>{desc}</desc>\n  </programme>')

            processed_channels.add(chan_id)

    xml_lines.append('</tv>')

    with open(M3U_FILENAME, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    with open(EPG_FILENAME, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))

if __name__ == "__main__":
    generate_files(fetch_data())

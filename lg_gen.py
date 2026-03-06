import json
import requests
import os
import time

# Configuration
API_URL = 'https://api.lgchannels.com/api/v1.0/schedulelist'
USER_AGENT = 'Mozilla/5.0 (Web0S; SmartTV) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.5735.110 Safari/537.36'
OUTPUT_DIR = "playlists"

# GitHub Details
GITHUB_USERNAME = "BuddyChewChew"
REPO_NAME = "lg-playlist-generator"

# Full List of 14 Regions
REGIONS = [
    {'name': 'United States', 'country': 'US', 'lang': 'en', 'suffix': 'us'},
    {'name': 'Canada', 'country': 'CA', 'lang': 'en', 'suffix': 'ca'},
    {'name': 'United Kingdom', 'country': 'GB', 'lang': 'en', 'suffix': 'uk'},
    {'name': 'Australia', 'country': 'AU', 'lang': 'en', 'suffix': 'au'},
    {'name': 'Germany', 'country': 'DE', 'lang': 'de', 'suffix': 'de'},
    {'name': 'France', 'country': 'FR', 'lang': 'fr', 'suffix': 'fr'},
    {'name': 'Spain', 'country': 'ES', 'lang': 'es', 'suffix': 'es'},
    {'name': 'Italy', 'country': 'IT', 'lang': 'it', 'suffix': 'it'},
    {'name': 'Brazil', 'country': 'BR', 'lang': 'pt', 'suffix': 'br'},
    {'name': 'Mexico', 'country': 'MX', 'lang': 'es', 'suffix': 'mx'},
    {'name': 'South Korea', 'country': 'KR', 'lang': 'ko', 'suffix': 'kr'},
    {'name': 'Japan', 'country': 'JP', 'lang': 'ja', 'suffix': 'jp'},
    {'name': 'New Zealand', 'country': 'NZ', 'lang': 'en', 'suffix': 'nz'},
    {'name': 'Singapore', 'country': 'SG', 'lang': 'en', 'suffix': 'sg'}
]

def generate_region_files(region):
    # Expanded headers to trick the API more effectively
    headers = {
        'User-Agent': USER_AGENT,
        'x-device-country': region['country'],
        'x-device-language': region['lang'],
        'x-device-model': 'LG-WM-2026',
        'Accept': 'application/json',
        'Connection': 'keep-alive'
    }
    
    print(f"🌍 Fetching: {region['name']} ({region['country']})")
    try:
        response = requests.get(API_URL, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"❌ Error for {region['name']}: {e}")
        return

    if not data or 'categories' not in data:
        print(f"⚠️ No channel data found for {region['name']}.")
        return

    # File paths
    m_file = f"lg_channels_{region['suffix']}.m3u"
    x_file = f"lg_channels_{region['suffix']}.xml"
    m_path = os.path.join(OUTPUT_DIR, m_file)
    x_path = os.path.join(OUTPUT_DIR, x_file)
    
    # EPG URL for the M3U Header
    epg_url = f"https://raw.githubusercontent.com/{GITHUB_USERNAME}/{REPO_NAME}/main/playlists/{x_file}"

    m3u_lines = [f'#EXTM3U x-tvg-url="{epg_url}"']
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

    with open(m_path, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    with open(x_path, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_lines))
    print(f"✅ Success: Generated {len(processed_channels)} channels for {region['name']}.")

if __name__ == "__main__":
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    for region in REGIONS:
        generate_region_files(region)
        time.sleep(1) # Small pause to avoid API rate limiting

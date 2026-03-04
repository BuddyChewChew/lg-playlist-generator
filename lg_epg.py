import requests
import json
import os
import sys
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.dom import minidom

class LGEPG:
    def __init__(self):
        self.url = 'https://api.lgchannels.com/api/v1.0/schedulelist'
        self.headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'x-device-country': 'US',
            'x-device-language': 'en',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def format_xml_time(self, ts):
        """Converts LG timestamp to XMLTV format"""
        try:
            return datetime.fromtimestamp(int(ts)).strftime('%Y%m%d%H%M%S +0000')
        except:
            return datetime.now().strftime('%Y%m%d%H%M%S +0000')

    def fetch_and_generate(self):
        print("Connecting to LG Channels API...")
        try:
            # Sending "{}" as data to fix the '411 Length Required' error
            response = requests.post(self.url, headers=self.headers, data="{}", timeout=30)
            
            if response.status_code != 200:
                print(f"Failed to fetch. Status: {response.status_code}")
                print(f"Response: {response.text}")
                return

            json_data = response.json()
            channels = json_data.get('data', [])
            
            if not channels:
                print("No channel data found in response.")
                return

            root = ET.Element("tv")
            root.set("generator-info-name", "LG Channels EPG")

            for channel in channels:
                chid = str(channel.get('channelId', ''))
                ch_name = channel.get('channelName', 'Unknown')
                ch_logo = channel.get('channelIcon', '')

                if not chid: continue

                # Channel Entry
                c_el = ET.SubElement(root, "channel", id=chid)
                ET.SubElement(c_el, "display-name").text = ch_name
                if ch_logo:
                    ET.SubElement(c_el, "icon", src=ch_logo)

                # Programme Entries
                programs = channel.get('programs', [])
                for prog in programs:
                    start = self.format_xml_time(prog.get('startTime'))
                    end = self.format_xml_time(prog.get('endTime'))
                    
                    p_el = ET.SubElement(root, "programme", start=start, stop=end, channel=chid)
                    ET.SubElement(p_el, "title", lang="en").text = prog.get('programName', 'No Title')
                    if prog.get('description'):
                        ET.SubElement(p_el, "desc", lang="en").text = prog.get('description')

            # Build XML String
            xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
            
            # Write the file
            with open("lg_channels.xml", "w", encoding="utf-8") as f:
                f.write(xml_str)
            
            print(f"Successfully created lg_channels.xml with {len(channels)} channels.")

        except Exception as e:
            print(f"Critical Error: {e}")

if __name__ == "__main__":
    LGEPG().fetch_and_generate()

Fork this for more languages: https://github.com/BuddyChewChew/lg-playlist-generator/issues/1#issuecomment-4041402810

# ⭐ LG WEB Channel M3U Playlist Generator

[![Update LG Playlist](https://github.com/BuddyChewChew/lg-playlist-generator/actions/workflows/update_lg.yml/badge.svg)](https://github.com/BuddyChewChew/lg-playlist-generator/actions/workflows/update_lg.yml)

This repository automatically generates M3U playlist files for LG Channels using a Python script and GitHub Actions. The playlists include embedded EPG (Electronic Program Guide) information via the `x-tvg-url` tag in the M3U header.

## 🟢 Service Status & Playlist URLs

| Service | Status | Region Support | Playlist URL (M3U) | EPG / Guide Source |
| :--- | :--- | :--- | :--- | :--- |
| **LG Channels** | ✅ Online | US (Live API) | `lg_channels_us.m3u` | `lg_channels_us.xml` (Self-Generated) |

---

## ▶️ How It Works

1. **Data Fetching:** A Python script (`lg_gen.py`) fetches the latest channel and program data directly from the LG Channels API.
2. **M3U Generation:** The script parses the live data, cleans stream URLs, and categorizes channels by genre.
3. **GitHub Action:** A scheduled workflow runs every 6 hours to ensure links and guide data are up to date.
4. **The TiviMate Fix:** The workflow dynamically injects the full GitHub Raw URL for the EPG into the M3U header. This ensures that players like TiviMate or OTT Navigator find the guide automatically.

## ▶️ Services Included

### 🔹 LG Channels (US)
**File:** `lg_channels_us.m3u`
* **Features:** Full linear lineup, channel logos, and 24-hour program descriptions.

---

## ▶️ EPG Script #2

All-In-One EPG: https://raw.githubusercontent.com/BuddyChewChew/lg-playlist-generator/refs/heads/main/LG_Channels_EPG_output/LG_Channels/all.xml.gz

Or single region .xml files. https://github.com/BuddyChewChew/lg-playlist-generator/tree/main/LG_Channels_EPG_output



## ▶️ Disclaimer

* This repository aggregates publicly available channel information.
* Availability and stability of streams depend entirely on the original service providers.
* Ensure your use of these streams complies with the terms of service of the respective platforms.

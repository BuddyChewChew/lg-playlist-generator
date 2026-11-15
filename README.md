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

## ▶️ Other Playlist Provided by (apsattv.com)

Working EPG: https://github.com/BuddyChewChew/lg-playlist-generator/raw/refs/heads/main/LG_Channels_EPG_output/all.xml.gz

LG Channels Playlists ( Updated 1/10/26)

LG Channels AE
https://www.apsattv.com/aelg.m3u

LG Channels AR
https://www.apsattv.com/arlg.m3u

LG Channels AT
https://www.apsattv.com/atlg.m3u

LG Channels AU
https://www.apsattv.com/aulg.m3u

LG Channels BE
https://www.apsattv.com/belg.m3u

LG Channels BR
https://www.apsattv.com/brlg.m3u

LG Channels CA
https://www.apsattv.com/calg.m3u

LG Channels CH
https://www.apsattv.com/chlg.m3u

LG Channels CL
https://www.apsattv.com/cllg.m3u

LG Channels CO
https://www.apsattv.com/colg.m3u

LG Channels DE
https://www.apsattv.com/delg.m3u

LG Channels DK
https://www.apsattv.com/dklg.m3u

LG Channels ES
https://www.apsattv.com/eslg.m3u

LG Channels FI
https://www.apsattv.com/filg.m3u

LG Channels FR
https://www.apsattv.com/frlg.m3u

LG Channels GB
https://www.apsattv.com/gblg.m3u

LG Channels IE
https://www.apsattv.com/ielg.m3u

LG Channels IN
https://www.apsattv.com/inlg.m3u

LG Channels IT
https://www.apsattv.com/itlg.m3u

LG Channels JP
https://www.apsattv.com/jplg.m3u

LG Channels KR
https://www.apsattv.com/krlg.m3u

LG Channels LU
https://www.apsattv.com/lulg.m3u

LG Channels MX
https://www.apsattv.com/mxlg.m3u

LG Channels NL
https://www.apsattv.com/nllg.m3u

LG Channels NO
https://www.apsattv.com/nolg.m3u

LG Channels NZ
https://www.apsattv.com/nzlg.m3u

LG Channels PE
https://www.apsattv.com/pelg.m3u

LG Channels PT
https://www.apsattv.com/ptlg.m3u

LG Channels PL
https://www.apsattv.com/pllg.m3u

LG Channels SG
https://www.apsattv.com/sglg.m3u

LG Channels SE
https://www.apsattv.com/selg.m3u

LG Channels US
https://www.apsattv.com/uslg.m3u

## ▶️ Disclaimer

* This repository aggregates publicly available channel information.
* Availability and stability of streams depend entirely on the original service providers.
* Ensure your use of these streams complies with the terms of service of the respective platforms.

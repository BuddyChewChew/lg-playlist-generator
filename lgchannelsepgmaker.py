#!/usr/bin/env python3
"""LG Channels EPG exporter (Optimized & Parallel). Python 3.9+, no dependencies.
Pulls XMLTV EPG data across all 33 verified regions concurrently."""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

AUTH_URL = 'https://PL.tv.wiselg.com/auth/11.0.0/authentication'
EPG_URL = 'https://EIC.tv.wiselg.com/cmp/api/v3.0/lgpapi/schedules?channelIdList=&zipcode='


class LGError(RuntimeError):
    def __init__(self, message, status=None, code=None):
        self.status, self.code = status, code
        super().__init__(message)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


def atomic_write(path, content, private=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.'+path.name+'-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
        os.chmod(temporary, 0o600 if private else 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class LGClient:
    def __init__(self, profile_path, timeout=30, country='PL', locale=None):
        self.path, self.timeout = Path(profile_path), timeout
        self.opener = build_opener(NoRedirect())
        if self.path.exists():
            try:
                self.profile = json.loads(self.path.read_text(encoding='utf-8-sig'))
                if not isinstance(self.profile.get('headers'), dict) or not isinstance(self.profile.get('authentication'), dict):
                    raise ValueError()
            except (OSError, ValueError, AttributeError):
                raise LGError('Invalid saved session; move or remove the session file and retry.') from None
        else:
            self.profile = {'headers': dict(DEVICE_HEADERS), 'authentication': {}}
        preset = COUNTRY_PRESETS[country]
        self.cluster = preset['cluster']
        self.auth_url = urlunsplit(urlsplit(AUTH_URL)._replace(netloc=self.cluster+'.tv.wiselg.com'))
        self.epg_url = urlunsplit(urlsplit(EPG_URL)._replace(netloc=self.cluster+'.tv.wiselg.com'))
        if self.profile.get('cluster') != self.cluster or self.profile.get('country') != country:
            self.profile['authentication'] = {}
        self.profile.update(cluster=self.cluster, country=country)
        locale = locale or preset['locale']
        self.profile['headers'].update({'X-Device-Country': country,
            'X-Device-Language': locale, 'X-Device-Locale': locale,
            'X-Device-Country-Group': preset['group']})

    def request(self, url, body=None, authenticated=False):
        headers = {k: v for k, v in self.profile['headers'].items() if k.lower() not in ('authorization', 'x-authentication')}
        if authenticated:
            token = self.profile['authentication']['accessToken']
            headers.update({'Authorization': token, 'X-Authentication': token})
        request = Request(url, data=body, headers=headers, method='POST' if body is not None else 'GET')
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(16_000_001)
        except HTTPError as error:
            code = None
            try:
                code = json.loads(error.read(8192)).get('error', {}).get('code')
            except Exception:
                pass
            status = error.code
            error.close()
            raise LGError(f'LG API returned HTTP {status}.', status, code) from None
        except OSError:
            raise LGError('Unable to connect to LG API.') from None
        if len(raw) > 16_000_000:
            raise LGError('LG response exceeds the 16 MB limit.')
        try:
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except ValueError:
            raise LGError('Invalid JSON from LG API.') from None

    @staticmethod
    def expiry(token):
        if not isinstance(token, str):
            return 0
        try:
            part = token.split('.')[1]
            result = float(json.loads(base64.urlsafe_b64decode(part+'='*(-len(part)%4)))['exp'])
            return result if math.isfinite(result) else 0
        except (ValueError, IndexError, KeyError, TypeError):
            return 0

    def refresh(self):
        refresh_token = self.profile['authentication'].get('refreshToken')
        body = urlencode({'refreshToken': refresh_token or ''}).encode('ascii')
        try:
            result = self.request(self.auth_url+'/refresh', body) if refresh_token else self.request(self.auth_url, b'LG SMARTTV')
        except LGError as error:
            if (error.status, error.code) != (406, 'AU.001.07'):
                raise
            result = self.request(self.auth_url, b'LG SMARTTV')
            created = result.get('authentication')
            if not isinstance(created, dict) or not isinstance(created.get('refreshToken'), str) or not created['refreshToken']:
                raise LGError('LG did not return a new session.')
        auth = result.get('authentication', result)
        if not isinstance(auth, dict) or self.expiry(auth.get('accessToken', '')) <= time.time()+30:
            raise LGError('LG did not return a valid access token.')
        self.profile['authentication'].update(auth)
        self.profile['saved_at_unix'] = time.time()
        atomic_write(self.path, json.dumps(self.profile, ensure_ascii=False, indent=2).encode('utf-8'), private=True)

    def fetch(self, force_refresh=False):
        if force_refresh or self.expiry(self.profile['authentication'].get('accessToken', '')) <= time.time()+120:
            self.refresh()
        try:
            return self.request(self.epg_url, authenticated=True)
        except LGError as error:
            if error.status != 401:
                raise
            self.refresh()
            return self.request(self.epg_url, authenticated=True)


def parse_date(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Missing timezone')
    return int(parsed.timestamp())


def normalize(data, channel_ids=None):
    items = data.get('channelList')
    if not isinstance(items, list):
        raise LGError('Missing channelList in LG response.')
    selected, channels, seen = set(channel_ids or []), [], set()
    for item in items:
        if not isinstance(item, dict):
            continue
        cid, name = item.get('channelId'), item.get('channelName')
        if not isinstance(cid, str) or not cid or not isinstance(name, str) or not name or cid in seen:
            continue
        if selected and cid not in selected:
            continue
        seen.add(cid)
        programmes, programme_keys = [], set()
        for event in item.get('scheduleList') or []:
            if not isinstance(event, dict) or not event.get('title'):
                continue
            try:
                start, stop = parse_date(event['startDateTime']), parse_date(event['endDateTime'])
            except (KeyError, TypeError, AttributeError, ValueError, OverflowError):
                continue
            key = (start, stop, event['title'])
            if stop <= start or key in programme_keys:
                continue
            programme_keys.add(key)
            programmes.append({'id': event.get('programId'), 'start': start, 'stop': stop,
                               'title': str(event['title']), 'description': str(event.get('description') or ''),
                               'category': str(event.get('genreName') or ''), 'image': event.get('programImg') or '',
                               'rating': event.get('ratingCode') or ''})
        channels.append({'id': cid, 'name': name, 'number': item.get('channelNumber'),
                         'logo': item.get('logoImg') or '', 'programmes': sorted(programmes, key=lambda e: e['start'])})
    if not channels:
        raise LGError('No EPG programmes found; previous export remains unchanged.')
    return {'schema': 1, 'country': 'PL', 'generated_at': datetime.now(timezone.utc).isoformat(),
            'source_timestamp': data.get('timestamp'), 'channels': channels}


def xmltv_bytes(data):
    root = ET.Element('tv', {'generator-info-name': 'LG Channels EPG'})
    def date(value):
        return datetime.fromtimestamp(value, timezone.utc).strftime('%Y%m%d%H%M%S +0000')
    for channel in data['channels']:
        element = ET.SubElement(root, 'channel', {'id': channel['id']})
        ET.SubElement(element, 'display-name', {'lang': data.get('language', 'en')}).text = channel['name']
        if channel['logo']:
            ET.SubElement(element, 'icon', {'src': channel['logo']})
    for channel in data['channels']:
        for event in channel['programmes']:
            element = ET.SubElement(root, 'programme', {'channel': channel['id'], 'start': date(event['start']), 'stop': date(event['stop'])})
            ET.SubElement(element, 'title', {'lang': data.get('language', 'en')}).text = event['title']
            for field, tag in [('description', 'desc'), ('category', 'category')]:
                if event[field]:
                    ET.SubElement(element, tag, {'lang': data.get('language', 'en')}).text = event[field]
            if event['image']:
                ET.SubElement(element, 'icon', {'src': event['image']})
            if event['rating']:
                rating = ET.SubElement(element, 'rating')
                ET.SubElement(rating, 'value').text = event['rating']
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)


DEVICE_HEADERS = {
    'X-Device-ID': 'aqrZHv0gBUDIb68TanQ6d/KUPUSJzZYnnsJ4W+66/DYNSbo3WV6AKliUE7M2VvPhxMH8o5uCOvq6FTxjvxrZzMynM3a7fwu6hc616w8lljERNAANMWISNY/tP9y714l9',
    'X-Device-Model': 'HE_DTV_W26P_AFADATAA', 'X-Device-Country': 'PL', 'X-Device-Language': 'pl-PL', 'X-Device-Locale': 'pl-PL',
    'X-Device-Country-Group': 'EU', 'X-Device-Product': 'webOSTV 26', 'X-Device-Platform': 'W26P', 'X-Device-SDK-VERSION': '11.2.0',
    'X-Device-Netcast-Platform-Version': '11.2.0', 'X-Device-Brand': 'LG', 'X-Device-Sales-Model': '43QNED80B6B.AEUJ6JP',
    'X-Device-Type': 'T01', 'X-Device-Eco-Info': '1', 'X-Caller-Id': 'com.webos.service.sdx', 'Accept': 'application/json',
    'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'LG SMARTTV',
    'X-Device-Eula': 'customAdAllowed,additional3Allowed,additionalDataAllowed,networkAllowed,chpAllowed,marketingOnAllowed,voice2Allowed,acrAdAllowed,generalTermsAllowed,shoppingOnAllowed,voiceAllowed,acrOnAllowed',
    'X-Device-FCK': '-1', 'X-Device-ContentsQA-Flag': 'N', 'X-Device-Remote-Flag': 'N', 'X-Device-Publish-Flag': 'N'
}

COUNTRY_PRESETS = {
    'AE': {'cluster': 'EIC', 'group': 'JA', 'locale': 'en-AE', 'name': 'United Arab Emirates', 'verified_channels': 89},
    'AR': {'cluster': 'AIC', 'group': 'AR', 'locale': 'en-AR', 'name': 'Argentina', 'verified_channels': 155},
    'AT': {'cluster': 'EIC', 'group': 'EU', 'locale': 'de-AT', 'name': 'Austria', 'verified_channels': 182},
    'AU': {'cluster': 'KIC', 'group': 'AJ', 'locale': 'en-AU', 'name': 'Australia', 'verified_channels': 169},
    'BE': {'cluster': 'EIC', 'group': 'EU', 'locale': 'nl-BE', 'name': 'Belgium', 'verified_channels': 78},
    'BR': {'cluster': 'AIC', 'group': 'BR', 'locale': 'pt-BR', 'name': 'Brazil', 'verified_channels': 225},
    'CA': {'cluster': 'AIC', 'group': 'CA', 'locale': 'en-CA', 'name': 'Canada', 'verified_channels': 237},
    'CH': {'cluster': 'EIC', 'group': 'EU', 'locale': 'de-CH', 'name': 'Switzerland', 'verified_channels': 189},
    'CL': {'cluster': 'AIC', 'group': 'CL', 'locale': 'en-CL', 'name': 'Chile', 'verified_channels': 154},
    'CO': {'cluster': 'AIC', 'group': 'CO', 'locale': 'en-CO', 'name': 'Colombia', 'verified_channels': 155},
    'DE': {'cluster': 'EIC', 'group': 'EU', 'locale': 'de-DE', 'name': 'Germany', 'verified_channels': 233},
    'DK': {'cluster': 'EIC', 'group': 'EU', 'locale': 'da-DK', 'name': 'Denmark', 'verified_channels': 215},
    'ES': {'cluster': 'EIC', 'group': 'EU', 'locale': 'es-ES', 'name': 'Spain', 'verified_channels': 211},
    'FI': {'cluster': 'EIC', 'group': 'EU', 'locale': 'fi-FI', 'name': 'Finland', 'verified_channels': 182},
    'FR': {'cluster': 'EIC', 'group': 'EU', 'locale': 'fr-FR', 'name': 'France', 'verified_channels': 202},
    'GB': {'cluster': 'EIC', 'group': 'EU', 'locale': 'en-GB', 'name': 'United Kingdom', 'verified_channels': 338},
    'IE': {'cluster': 'EIC', 'group': 'EU', 'locale': 'en-IE', 'name': 'Ireland', 'verified_channels': 161},
    'IN': {'cluster': 'KIC', 'group': 'AJ', 'locale': 'en-IN', 'name': 'India', 'verified_channels': 177},
    'IT': {'cluster': 'EIC', 'group': 'EU', 'locale': 'it-IT', 'name': 'Italy', 'verified_channels': 203},
    'JP': {'cluster': 'KIC', 'group': 'JP', 'locale': 'ja-JP', 'name': 'Japan', 'verified_channels': 20},
    'KR': {'cluster': 'KIC', 'group': 'KR', 'locale': 'ko-KR', 'name': 'South Korea', 'verified_channels': 112},
    'LU': {'cluster': 'EIC', 'group': 'EU', 'locale': 'en-LU', 'name': 'Luxembourg', 'verified_channels': 70},
    'MX': {'cluster': 'AIC', 'group': 'MX', 'locale': 'es-MX', 'name': 'Mexico', 'verified_channels': 217},
    'NL': {'cluster': 'EIC', 'group': 'EU', 'locale': 'nl-NL', 'name': 'Netherlands', 'verified_channels': 191},
    'NO': {'cluster': 'EIC', 'group': 'EU', 'locale': 'nb-NO', 'name': 'Norway', 'verified_channels': 215},
    'NZ': {'cluster': 'KIC', 'group': 'AJ', 'locale': 'en-NZ', 'name': 'New Zealand', 'verified_channels': 119},
    'PE': {'cluster': 'AIC', 'group': 'PE', 'locale': 'en-PE', 'name': 'Peru', 'verified_channels': 155},
    'PL': {'cluster': 'EIC', 'group': 'EU', 'locale': 'pl-PL', 'name': 'Poland', 'verified_channels': 58},
    'PT': {'cluster': 'EIC', 'group': 'EU', 'locale': 'pt-PT', 'name': 'Portugal', 'verified_channels': 74},
    'SE': {'cluster': 'EIC', 'group': 'EU', 'locale': 'sv-SE', 'name': 'Sweden', 'verified_channels': 218},
    'SG': {'cluster': 'KIC', 'group': 'AJ', 'locale': 'en-SG', 'name': 'Singapore', 'verified_channels': 55},
    'TW': {'cluster': 'KIC', 'group': 'TW', 'locale': 'en-TW', 'name': 'Taiwan', 'verified_channels': 78},
    'US': {'cluster': 'AIC', 'group': 'US', 'locale': 'en-US', 'name': 'USA', 'verified_channels': 459}
}
LOCALES = {code: preset["locale"] for code, preset in COUNTRY_PRESETS.items()}


def export_country_epg(country, locale, output, timeout, refresh):
    try:
        client = LGClient(output / f'.lg_session_{country}.json', timeout, country, locale)
        data = normalize(client.fetch(refresh))
        data.update(country=country, language=locale.split('-')[0])
        stem = 'LG_Channels_' + country
        atomic_write(output / f'{stem}.xml', xmltv_bytes(data))
        programmes = sum(len(c['programmes']) for c in data['channels'])
        print(f'{country}: EPG channels={len(data["channels"])}, programmes={programmes}')
        return country, None
    except (LGError, OSError) as error:
        return country, str(error)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument('--countries', '--country', nargs='+', help='Verified country codes, e.g. PL DE GB NZ, or ALL (UK is accepted as GB)')
    selection.add_argument('--all', action='store_true', default=True, help='Export all 33 verified countries (default)')
    parser.add_argument('--locale', help='Override locale, e.g. fr-CA; requires a single country')
    parser.add_argument('--output-dir', default='LG_Channels_EPG_output')
    parser.add_argument('--timeout', type=int, default=30)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--list-countries', action='store_true', help='Show all 33 verified countries, regions and reference channel counts')
    parser.add_argument('--workers', type=int, default=8, help='Concurrent worker threads for parallel fetching')
    args = parser.parse_args(argv)

    if args.list_countries:
        print('33 country catalogues verified on 2026-10-18.')
        for country, preset in COUNTRY_PRESETS.items():
            print(f"{country}  - {preset['name']:<22} cluster={preset['cluster']} channels={preset['verified_channels']}")
        return 0

    selected = ['ALL'] if (args.all or not args.countries) else args.countries
    countries = []
    for part in selected:
        for country in part.replace(',', ' ').split():
            country = country.upper()
            country = 'GB' if country == 'UK' else country
            if country == 'ALL':
                countries = list(COUNTRY_PRESETS)
                continue
            if country not in COUNTRY_PRESETS:
                parser.error('Unsupported country code: ' + country + '. Use --list-countries.')
            if country not in countries:
                countries.append(country)

    if not countries or (args.locale and len(countries) != 1):
        parser.error('--locale requires exactly one country.')
    if args.locale and not re.fullmatch(r'[a-z]{2}-[A-Z]{2}', args.locale):
        parser.error('Locale must have the form xx-XX.')
    if not 1 <= args.timeout <= 300:
        parser.error('--timeout must be between 1 and 300 seconds.')

    output = Path(args.output_dir).expanduser().resolve()
    failures = 0

    print(f'Fetching EPG for {len(countries)} region(s) using {args.workers} workers...')
    with ThreadPoolExecutor(max_workers=min(args.workers, len(countries))) as executor:
        futures = {
            executor.submit(export_country_epg, country, args.locale or LOCALES.get(country, f'en-{country}'), output, args.timeout, args.refresh): country
            for country in countries
        }
        for future in as_completed(futures):
            country, err = future.result()
            if err:
                failures += 1
                print(f'{country}: {err}', file=sys.stderr)

    print('Output directory: ' + str(output))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
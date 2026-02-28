"""
SONOS Controller LogicBlock (v1.4) - All-in-One

Steuert und überwacht einen Sonos-Lautsprecher über die lokale UPnP/SOAP-API (Port 1400).
Remanent: Einstellungen (Volume, Bass, Treble, IP etc.) werden über Reboots gespeichert.
Play/Pause/Stop werden NICHT gespeichert (Befehle, keine Settings).

Funktionen:
- Play/Pause/Stop/Next/Previous
- Volume, Bass, Treble, Loudness, Mute, Playmode, Crossfade
- Radio/Stream/Favoriten/Streaming-Container abspielen
- TTS/Ansagen mit automatischer Zustandswiederherstellung
- Nachtmodus (Soundbar/Beam/Arc)
- iTunes Cover/Genre Lookup
- Genre-basierte Farbanimation (5-Farben-Paletten)
- Favoriten-Cache, Gruppen-Erkennung, Streaming-Dienst Erkennung
- Reconnect mit exponentiellem Backoff

Basiert auf dem EDOMI SONOS Controller v8.5 (19000508), portiert auf das
asynchrone LogicBlock-Framework.
"""

import asyncio
import aiohttp
import logging
import json
import os
import re
from datetime import datetime
from html import escape as html_escape, unescape as html_unescape
from typing import Dict, Optional, Any, List, Tuple
from urllib.parse import quote

try:
    from ..base import LogicBlock
except ImportError:
    from logic.base import LogicBlock

logger = logging.getLogger(__name__)


# ============================================================================
# STREAMING-DIENST ERKENNUNG
# ============================================================================

STREAMING_SERVICES = [
    ('x-sonos-spotify:', 'Spotify'),
    ('x-sonosapi-radio:', 'TuneIn'),
    ('x-sonosapi-stream:', 'TuneIn'),
    ('x-sonosapi-hls:', 'TuneIn'),
    ('x-sonos-http:amz', 'Amazon Music'),
    ('x-sonosapi-rtrecent:', 'Amazon Music'),
    ('aac://https://amazon', 'Amazon Music'),
    ('x-sonos-http:scrobbling', 'Last.fm'),
    ('x-sonos-http:track:', 'Deezer'),
    ('x-sonos-http:library', 'Bibliothek'),
    ('x-file-cifs:', 'Netzwerk'),
    ('x-rincon-mp3radio:', 'Radio (MP3)'),
    ('x-rincon-playlist:', 'Playlist'),
    ('x-rincon-queue:', 'Queue'),
    ('x-rincon:', 'Gruppe'),
    ('x-sonosapi-hls-static:', 'Apple Music'),
    ('x-sonos-http:song:', 'Apple Music'),
    ('x-sonosprog-http:', 'Sonos Radio'),
    ('x-soco-tc:', 'Alexa'),
    ('http://', 'HTTP Stream'),
    ('https://', 'HTTPS Stream'),
]


def detect_streaming_service(uri):
    """Erkennt den Streaming-Dienst aus der URI"""
    if not uri:
        return ''
    uri_lower = uri.lower()
    for pattern, name in STREAMING_SERVICES:
        if pattern.lower() in uri_lower:
            return name
    return 'Unbekannt'


def is_radio_uri(uri):
    """Prüft ob die URI ein Radio-Stream ist"""
    if not uri:
        return False
    return any(p in uri for p in [
        'x-sonosapi-stream', 'x-sonosapi-radio', 'x-rincon-mp3radio'
    ])


# ============================================================================
# STREAM-CONTENT PARSER
# ============================================================================

def parse_stream_content(stream):
    """
    Parst verschiedene streamContent-Formate:
    - "Artist - Titel"
    - "Jetzt on Air: Artist und Titel"
    - "Now Playing: Artist - Titel"
    - "Artist: Titel"
    - "Artist / Titel"
    """
    artist = ''
    title = ''
    stream = (stream or '').strip()

    if not stream:
        return {'artist': '', 'title': ''}

    # Format 1: "Artist - Titel" (Standard)
    if ' - ' in stream:
        parts = stream.split(' - ', 1)
        artist = parts[0].strip()
        title = parts[1].strip()
        for prefix in ['Now Playing:', 'Jetzt:', 'Playing:', 'Aktuell:']:
            if artist.lower().startswith(prefix.lower()):
                artist = artist[len(prefix):].strip()
                break

    # Format 2: "Jetzt on Air: Artist und Titel"
    elif re.match(r'^Jetzt\s+on\s+Air:\s*(.+?)\s+und\s+(.+)$', stream, re.I):
        m = re.match(r'^Jetzt\s+on\s+Air:\s*(.+?)\s+und\s+(.+)$', stream, re.I)
        artist, title = m.group(1).strip(), m.group(2).strip()

    # Format 3: "On Air: Artist und Titel"
    elif re.match(r'^On\s+Air:\s*(.+?)\s+und\s+(.+)$', stream, re.I):
        m = re.match(r'^On\s+Air:\s*(.+?)\s+und\s+(.+)$', stream, re.I)
        artist, title = m.group(1).strip(), m.group(2).strip()

    # Format 4: "Artist: Titel"
    elif ': ' in stream and ' - ' not in stream:
        parts = stream.split(': ', 1)
        known = ['jetzt', 'now', 'playing', 'on air', 'aktuell', 'current']
        if parts[0].strip().lower() not in known:
            artist, title = parts[0].strip(), parts[1].strip()

    # Format 5: "Artist / Titel"
    elif ' / ' in stream:
        parts = stream.split(' / ', 1)
        artist, title = parts[0].strip(), parts[1].strip()

    return {'artist': artist, 'title': title}


# ============================================================================
# TRACK-POSITION
# ============================================================================

def time_to_seconds(time_str):
    """Konvertiert HH:MM:SS oder MM:SS zu Sekunden"""
    if not time_str:
        return 0
    parts = time_str.split(':')
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def calculate_track_percent(rel_time, duration):
    """Berechnet Track-Position in Prozent (0-100)"""
    current = time_to_seconds(rel_time)
    total = time_to_seconds(duration)
    if total <= 0:
        return 0
    return max(0, min(100, round((current / total) * 100)))


# ============================================================================
# GRUPPENROLLE
# ============================================================================

def determine_group_role(zone_info, media_info):
    """Ermittelt Gruppenrolle: Standalone, Master oder Slave"""
    group_name = zone_info.get('CurrentZoneGroupName', '')
    if ' + ' not in group_name:
        return 'Standalone'

    current_uri = media_info.get('CurrentURI', '')
    if current_uri.startswith('x-rincon:'):
        return 'Slave'
    return 'Master'


def get_group_members(zone_info):
    """Gibt Gruppenmitglieder als Pipe-getrennte Liste zurück"""
    group_name = zone_info.get('CurrentZoneGroupName', '')
    if ' + ' in group_name:
        return group_name.replace(' + ', '|')
    return group_name


# ============================================================================
# ITUNES API
# ============================================================================

async def get_itunes_info(artist, title, cache=None):
    """
    Sucht Album-Cover und Genre über iTunes API.
    Gibt dict mit 'cover' und 'genre' zurück oder None.
    """
    if not artist or not title:
        return None

    artist = artist.strip()
    title = title.strip()

    # Cache prüfen
    cache_key = '{}:{}'.format(artist.lower(), title.lower())
    if cache and cache.get('key') == cache_key:
        return {'cover': cache.get('cover', ''), 'genre': cache.get('genre', '')}

    # Sonderzeichen entfernen
    clean_artist = re.sub(r'[^\w\s\-äöüÄÖÜß]', '', artist)
    clean_title = re.sub(r'[^\w\s\-äöüÄÖÜß]', '', title)

    search_term = quote('{} {}'.format(clean_artist, clean_title))
    url = "https://itunes.apple.com/search?term={}&media=music&entity=song&limit=1".format(search_term)

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5),
                    headers={'User-Agent': 'SONOS-LogicBlock/1.0'}
                ) as resp:
                    if resp.status == 200:
                        data = json.loads(await resp.text())
                        if data.get('results'):
                            result = data['results'][0]
                            cover = result.get('artworkUrl100', '')
                            if cover:
                                cover = cover.replace('100x100', '600x600')
                            genre = result.get('primaryGenreName', '')

                            # Cache aktualisieren
                            if cache is not None:
                                cache['key'] = cache_key
                                cache['cover'] = cover
                                cache['genre'] = genre

                            return {'cover': cover, 'genre': genre}
                        return None

                    elif resp.status in (429, 500, 502, 503):
                        await asyncio.sleep(2 ** attempt)
                        continue
                    else:
                        return None
        except Exception as e:
            logger.error("[iTunes] Attempt {} error: {}".format(attempt + 1, e))
            if attempt < 2:
                await asyncio.sleep(1)

    return None


# ============================================================================
# GENRE-FARBPALETTEN (5 Farben pro Genre)
# ============================================================================

GENRE_PALETTES = {
    'pop': [(240, 188, 36), (250, 138, 37), (224, 49, 22), (250, 45, 191), (147, 49, 240)],
    'rock': [(139, 0, 0), (255, 0, 0), (255, 69, 0), (255, 140, 0), (178, 34, 34)],
    'metal': [(20, 20, 20), (139, 0, 0), (169, 169, 169), (255, 0, 0), (105, 105, 105)],
    'punk': [(255, 0, 0), (0, 0, 0), (255, 255, 0), (255, 0, 255), (0, 255, 0)],
    'electronic': [(0, 255, 255), (0, 0, 255), (128, 0, 255), (255, 0, 255), (255, 20, 147)],
    'dance': [(255, 0, 255), (0, 255, 255), (255, 255, 0), (255, 0, 128), (0, 255, 128)],
    'techno': [(0, 0, 255), (128, 0, 255), (0, 255, 255), (255, 0, 128), (0, 128, 255)],
    'house': [(255, 0, 255), (255, 105, 180), (238, 130, 238), (218, 112, 214), (186, 85, 211)],
    'hip-hop': [(128, 0, 128), (75, 0, 130), (0, 128, 128), (255, 20, 147), (255, 215, 0)],
    'hip hop': [(128, 0, 128), (75, 0, 130), (0, 128, 128), (255, 20, 147), (255, 215, 0)],
    'r&b': [(148, 0, 211), (186, 85, 211), (255, 20, 147), (255, 182, 193), (138, 43, 226)],
    'rap': [(255, 215, 0), (255, 140, 0), (128, 0, 128), (0, 0, 0), (255, 0, 0)],
    'jazz': [(0, 102, 204), (70, 130, 180), (0, 139, 139), (95, 158, 160), (25, 25, 112)],
    'blues': [(0, 0, 139), (65, 105, 225), (100, 149, 237), (0, 0, 205), (25, 25, 112)],
    'classical': [(255, 215, 0), (247, 231, 206), (255, 255, 240), (128, 0, 32), (65, 105, 225)],
    'klassik': [(255, 215, 0), (247, 231, 206), (255, 255, 240), (128, 0, 32), (65, 105, 225)],
    'country': [(139, 90, 43), (210, 105, 30), (255, 140, 0), (107, 142, 35), (245, 222, 179)],
    'folk': [(160, 82, 45), (210, 180, 140), (85, 107, 47), (189, 183, 107), (244, 164, 96)],
    'reggae': [(0, 128, 0), (255, 255, 0), (255, 0, 0), (34, 139, 34), (255, 215, 0)],
    'latin': [(255, 0, 0), (255, 69, 0), (255, 215, 0), (255, 20, 147), (0, 206, 209)],
    'salsa': [(255, 69, 0), (255, 0, 0), (255, 215, 0), (255, 140, 0), (220, 20, 60)],
    'indie': [(64, 224, 208), (255, 127, 80), (152, 251, 152), (184, 134, 11), (224, 176, 255)],
    'alternative': [(128, 128, 128), (0, 128, 128), (255, 99, 71), (106, 90, 205), (255, 215, 0)],
    'ambient': [(135, 206, 250), (230, 230, 250), (152, 251, 152), (255, 218, 185), (255, 182, 193)],
    'chill': [(176, 224, 230), (221, 160, 221), (240, 255, 240), (255, 245, 238), (230, 230, 250)],
    'soul': [(255, 140, 0), (139, 69, 19), (255, 215, 0), (0, 206, 209), (255, 20, 147)],
    'funk': [(255, 0, 255), (255, 140, 0), (255, 215, 0), (0, 255, 255), (255, 105, 180)],
    'schlager': [(100, 149, 237), (255, 182, 193), (255, 255, 0), (144, 238, 144), (255, 165, 0)],
    'christmas': [(255, 0, 0), (0, 128, 0), (255, 215, 0), (255, 250, 250), (178, 34, 34)],
    'holiday': [(0, 128, 0), (255, 0, 0), (255, 215, 0), (255, 255, 255), (192, 192, 192)],
    'default': [(255, 200, 150), (245, 222, 179), (244, 164, 96), (255, 248, 220), (255, 185, 15)],
}


def get_genre_palette(genre):
    """Gibt die 5-Farben-Palette für ein Genre zurück"""
    genre_lower = genre.lower().strip() if genre else 'default'

    # Exakte Übereinstimmung
    if genre_lower in GENRE_PALETTES:
        return GENRE_PALETTES[genre_lower]

    # Teilübereinstimmung
    for key, palette in GENRE_PALETTES.items():
        if key in genre_lower or genre_lower in key:
            return palette

    return GENRE_PALETTES['default']


def rgb_to_hex(r, g, b):
    """RGB zu HEX String"""
    return "#{:02X}{:02X}{:02X}".format(r, g, b)


def rgb_to_str(r, g, b):
    """RGB zu String"""
    return "{},{},{}".format(r, g, b)


def move_towards(current, target, step=15):
    """Bewegt Wert einen Schritt Richtung Ziel"""
    if current < target:
        return min(current + step, target)
    elif current > target:
        return max(current - step, target)
    return current


# ============================================================================
# SONOS UPnP/SOAP COMMUNICATION
# ============================================================================

SERVICE_PATHS = {
    'AVTransport': '/MediaRenderer/AVTransport/Control',
    'RenderingControl': '/MediaRenderer/RenderingControl/Control',
    'ZoneGroupTopology': '/ZoneGroupTopology/Control',
    'ContentDirectory': '/MediaServer/ContentDirectory/Control',
}

SERVICE_URNS = {
    'AVTransport': 'urn:schemas-upnp-org:service:AVTransport:1',
    'RenderingControl': 'urn:schemas-upnp-org:service:RenderingControl:1',
    'ZoneGroupTopology': 'urn:schemas-upnp-org:service:ZoneGroupTopology:1',
    'ContentDirectory': 'urn:schemas-upnp-org:service:ContentDirectory:1',
}

CONNECTION_TIMEOUT = 5
SOAP_TIMEOUT = 8


class SonosSoap:
    """Async SOAP client for Sonos UPnP API"""

    def __init__(self, ip):
        self.ip = ip
        self._base_url = "http://{}:1400".format(ip)

    async def soap_request(self, service, action, body, timeout=SOAP_TIMEOUT):
        """Führt einen SOAP Request aus und gibt die Response zurück"""
        path = SERVICE_PATHS.get(service, SERVICE_PATHS['AVTransport'])
        urn = SERVICE_URNS.get(service, SERVICE_URNS['AVTransport'])

        envelope = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
            '<s:Body>{}</s:Body>'
            '</s:Envelope>'
        ).format(body)

        headers = {
            'Content-Type': 'text/xml; charset="utf-8"',
            'SOAPACTION': '"{}#{}"'.format(urn, action),
        }

        url = self._base_url + path

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, data=envelope, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as resp:
                    return await resp.text()
        except Exception as e:
            logger.error("[SOAP] {} {} error: {}".format(service, action, e))
            return None

    # ============ AVTransport ============

    async def get_transport_info(self):
        """Transport-Status: 1=Playing, 2=Paused, 3=Stopped"""
        body = (
            '<u:GetTransportInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '</u:GetTransportInfo>'
        )
        resp = await self.soap_request('AVTransport', 'GetTransportInfo', body)
        if resp is None:
            return None

        m = re.search(r'<CurrentTransportState>(\w+)</CurrentTransportState>', resp)
        if m:
            state_map = {'PLAYING': 1, 'PAUSED_PLAYBACK': 2, 'STOPPED': 3, 'TRANSITIONING': 1}
            return state_map.get(m.group(1), 3)
        return None

    async def get_media_info(self):
        """Holt MediaInfo (CurrentURI, title, etc.)"""
        body = (
            '<u:GetMediaInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '</u:GetMediaInfo>'
        )
        resp = await self.soap_request('AVTransport', 'GetMediaInfo', body)
        if resp is None:
            return {}

        result = {}
        for tag in ['CurrentURI', 'CurrentURIMetaData']:
            m = re.search(r'<{0}>(.*?)</{0}>'.format(tag), resp, re.DOTALL)
            if m:
                result[tag] = html_unescape(m.group(1))

        # Title aus MetaData extrahieren
        meta = result.get('CurrentURIMetaData', '')
        if meta:
            decoded = html_unescape(meta)
            tm = re.search(r'<dc:title>(.*?)</dc:title>', decoded)
            if tm:
                result['title'] = html_unescape(tm.group(1))

        return result

    async def get_position_info(self):
        """Holt PositionInfo (Track, RelTime, Duration, TrackURI, Artist, Title, Album, Cover)"""
        body = (
            '<u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '</u:GetPositionInfo>'
        )
        resp = await self.soap_request('AVTransport', 'GetPositionInfo', body)
        if resp is None:
            return {}

        result = {}
        for tag in ['Track', 'RelTime', 'TrackDuration', 'TrackURI']:
            m = re.search(r'<{0}>(.*?)</{0}>'.format(tag), resp, re.DOTALL)
            if m:
                result[tag] = m.group(1)

        m = re.search(r'<TrackMetaData>(.*?)</TrackMetaData>', resp, re.DOTALL)
        if m:
            meta = html_unescape(m.group(1))
            result['TrackMetaData'] = meta

            sc = re.search(r'<r:streamContent>(.*?)</r:streamContent>', meta)
            if sc:
                result['streamContent'] = html_unescape(sc.group(1))

            for dc_tag, key in [('dc:title', 'title'), ('dc:creator', 'artist'),
                                ('upnp:album', 'album')]:
                dm = re.search(r'<{0}>(.*?)</{0}>'.format(dc_tag), meta)
                if dm:
                    result[key] = html_unescape(dm.group(1))

            art = re.search(r'<upnp:albumArtURI>(.*?)</upnp:albumArtURI>', meta)
            if art:
                uri = html_unescape(art.group(1))
                if not uri.startswith('http'):
                    uri = 'http://{}:1400{}'.format(self.ip, uri)
                result['albumArtURI'] = uri

        return result

    async def play(self):
        body = (
            '<u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID><Speed>1</Speed></u:Play>'
        )
        resp = await self.soap_request('AVTransport', 'Play', body)
        return resp is not None and 'PlayResponse' in (resp or '')

    async def pause(self):
        body = (
            '<u:Pause xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID></u:Pause>'
        )
        resp = await self.soap_request('AVTransport', 'Pause', body)
        return resp is not None

    async def stop(self):
        body = (
            '<u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID></u:Stop>'
        )
        resp = await self.soap_request('AVTransport', 'Stop', body)
        return resp is not None

    async def next(self):
        body = (
            '<u:Next xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID></u:Next>'
        )
        resp = await self.soap_request('AVTransport', 'Next', body)
        return resp is not None

    async def previous(self):
        body = (
            '<u:Previous xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID></u:Previous>'
        )
        resp = await self.soap_request('AVTransport', 'Previous', body)
        return resp is not None

    async def set_radio(self, uri, title=''):
        """Setzt Radio-URI mit korrekten TuneIn-Metadaten (wie Gira/EDOMI)"""
        # Station-ID aus URI extrahieren für Metadaten
        station_id = ''
        m = re.search(r'x-sonosapi-stream:(\w+)', uri)
        if m:
            station_id = m.group(1)

        # DIDL-Lite Metadaten wie im Gira-Baustein - SA_RINCON65031_ ist der TuneIn Service Descriptor
        if not title:
            title = station_id or 'Radio'
        meta = (
            '&lt;DIDL-Lite xmlns:dc=&quot;http://purl.org/dc/elements/1.1/&quot; '
            'xmlns:upnp=&quot;urn:schemas-upnp-org:metadata-1-0/upnp/&quot; '
            'xmlns:r=&quot;urn:schemas-rinconnetworks-com:metadata-1-0/&quot; '
            'xmlns=&quot;urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/&quot;&gt;'
            '&lt;item id=&quot;F00092020{sid}&quot; parentID=&quot;L&quot; restricted=&quot;true&quot;&gt;'
            '&lt;dc:title&gt;{title}&lt;/dc:title&gt;'
            '&lt;upnp:class&gt;object.item.audioItem.audioBroadcast&lt;/upnp:class&gt;'
            '&lt;desc id=&quot;cdudn&quot; nameSpace=&quot;urn:schemas-rinconnetworks-com:metadata-1-0/&quot;&gt;'
            'SA_RINCON65031_&lt;/desc&gt;'
            '&lt;/item&gt;&lt;/DIDL-Lite&gt;'
        ).format(sid=station_id, title=html_escape(title))

        body = (
            '<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '<CurrentURI>{}</CurrentURI>'
            '<CurrentURIMetaData>{}</CurrentURIMetaData>'
            '</u:SetAVTransportURI>'
        ).format(html_escape(uri), meta)

        resp = await self.soap_request('AVTransport', 'SetAVTransportURI', body)
        return resp is not None and ('SetAVTransportURIResponse' in (resp or '') or '200 OK' in (resp or ''))

    async def set_av_transport_uri(self, uri, meta=''):
        body = (
            '<u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '<CurrentURI>{}</CurrentURI>'
            '<CurrentURIMetaData>{}</CurrentURIMetaData>'
            '</u:SetAVTransportURI>'
        ).format(html_escape(uri), meta)
        resp = await self.soap_request('AVTransport', 'SetAVTransportURI', body)
        return resp is not None

    async def add_to_queue(self, uri, meta=''):
        body = (
            '<u:AddURIToQueue xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '<EnqueuedURI>{}</EnqueuedURI>'
            '<EnqueuedURIMetaData>{}</EnqueuedURIMetaData>'
            '<DesiredFirstTrackNumberEnqueued>0</DesiredFirstTrackNumberEnqueued>'
            '<EnqueueAsNext>0</EnqueueAsNext>'
            '</u:AddURIToQueue>'
        ).format(html_escape(uri), meta)
        resp = await self.soap_request('AVTransport', 'AddURIToQueue', body)
        return resp is not None and 'AddURIToQueueResponse' in (resp or '')

    async def clear_queue(self):
        body = (
            '<u:RemoveAllTracksFromQueue xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '</u:RemoveAllTracksFromQueue>'
        )
        resp = await self.soap_request('AVTransport', 'RemoveAllTracksFromQueue', body)
        return resp is not None

    async def set_track(self, track_nr):
        body = (
            '<u:Seek xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '<Unit>TRACK_NR</Unit>'
            '<Target>{}</Target>'
            '</u:Seek>'
        ).format(track_nr)
        resp = await self.soap_request('AVTransport', 'Seek', body)
        return resp is not None

    async def get_current_playlist(self):
        """Holt die aktuelle Queue/Playlist - gibt Anzahl der Tracks zurück"""
        body = (
            '<u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">'
            '<ObjectID>Q:0</ObjectID>'
            '<BrowseFlag>BrowseDirectChildren</BrowseFlag>'
            '<Filter>dc:title</Filter>'
            '<StartingIndex>0</StartingIndex>'
            '<RequestedCount>1000</RequestedCount>'
            '<SortCriteria></SortCriteria>'
            '</u:Browse>'
        )
        resp = await self.soap_request('ContentDirectory', 'Browse', body)
        if resp is None:
            return 0
        # Zähle die Items in der Response
        count = resp.count('<item')
        return count

    async def remove_from_queue(self, track_nr):
        """Entfernt einen Track aus der Queue"""
        body = (
            '<u:RemoveTrackFromQueue xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '<ObjectID>Q:0/{}</ObjectID>'
            '<UpdateID>0</UpdateID>'
            '</u:RemoveTrackFromQueue>'
        ).format(track_nr)
        resp = await self.soap_request('AVTransport', 'RemoveTrackFromQueue', body)
        return resp is not None

    async def get_transport_settings(self):
        """Playmode: 0=NORMAL, 1=REPEAT_ALL, 2=SHUFFLE_NOREPEAT, 3=SHUFFLE"""
        body = (
            '<u:GetTransportSettings xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '</u:GetTransportSettings>'
        )
        resp = await self.soap_request('AVTransport', 'GetTransportSettings', body)
        if resp is None:
            return None
        m = re.search(r'<PlayMode>(\w+)</PlayMode>', resp)
        if m:
            mode_map = {'NORMAL': 0, 'REPEAT_ALL': 1, 'SHUFFLE_NOREPEAT': 2, 'SHUFFLE': 3}
            return mode_map.get(m.group(1), 0)
        return None

    async def set_play_mode(self, mode):
        mode_map = {0: 'NORMAL', 1: 'REPEAT_ALL', 2: 'SHUFFLE_NOREPEAT', 3: 'SHUFFLE'}
        mode_str = mode_map.get(mode, 'NORMAL')
        body = (
            '<u:SetPlayMode xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '<NewPlayMode>{}</NewPlayMode>'
            '</u:SetPlayMode>'
        ).format(mode_str)
        resp = await self.soap_request('AVTransport', 'SetPlayMode', body)
        return resp is not None

    async def get_crossfade_mode(self):
        body = (
            '<u:GetCrossfadeMode xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '</u:GetCrossfadeMode>'
        )
        resp = await self.soap_request('AVTransport', 'GetCrossfadeMode', body)
        if resp is None:
            return None
        m = re.search(r'<CrossfadeMode>(\d)</CrossfadeMode>', resp)
        return bool(int(m.group(1))) if m else None

    async def set_crossfade_mode(self, enabled):
        body = (
            '<u:SetCrossfadeMode xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            '<InstanceID>0</InstanceID>'
            '<CrossfadeMode>{}</CrossfadeMode>'
            '</u:SetCrossfadeMode>'
        ).format(1 if enabled else 0)
        resp = await self.soap_request('AVTransport', 'SetCrossfadeMode', body)
        return resp is not None

    # ============ RenderingControl ============

    async def get_volume(self):
        body = (
            '<u:GetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><Channel>Master</Channel>'
            '</u:GetVolume>'
        )
        resp = await self.soap_request('RenderingControl', 'GetVolume', body)
        if resp is None:
            return None
        m = re.search(r'<CurrentVolume>(\d+)</CurrentVolume>', resp)
        return int(m.group(1)) if m else None

    async def set_volume(self, volume):
        volume = max(0, min(100, volume))
        body = (
            '<u:SetVolume xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><Channel>Master</Channel>'
            '<DesiredVolume>{}</DesiredVolume>'
            '</u:SetVolume>'
        ).format(volume)
        resp = await self.soap_request('RenderingControl', 'SetVolume', body)
        return resp is not None

    async def get_mute(self):
        body = (
            '<u:GetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><Channel>Master</Channel>'
            '</u:GetMute>'
        )
        resp = await self.soap_request('RenderingControl', 'GetMute', body)
        if resp is None:
            return None
        m = re.search(r'<CurrentMute>(\d)</CurrentMute>', resp)
        return bool(int(m.group(1))) if m else None

    async def set_mute(self, mute):
        body = (
            '<u:SetMute xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><Channel>Master</Channel>'
            '<DesiredMute>{}</DesiredMute>'
            '</u:SetMute>'
        ).format(1 if mute else 0)
        resp = await self.soap_request('RenderingControl', 'SetMute', body)
        return resp is not None

    async def get_bass(self):
        body = (
            '<u:GetBass xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID></u:GetBass>'
        )
        resp = await self.soap_request('RenderingControl', 'GetBass', body)
        if resp is None:
            return None
        m = re.search(r'<CurrentBass>(-?\d+)</CurrentBass>', resp)
        return int(m.group(1)) if m else None

    async def set_bass(self, bass):
        bass = max(-10, min(10, bass))
        body = (
            '<u:SetBass xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><DesiredBass>{}</DesiredBass>'
            '</u:SetBass>'
        ).format(bass)
        resp = await self.soap_request('RenderingControl', 'SetBass', body)
        return resp is not None

    async def get_treble(self):
        body = (
            '<u:GetTreble xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID></u:GetTreble>'
        )
        resp = await self.soap_request('RenderingControl', 'GetTreble', body)
        if resp is None:
            return None
        m = re.search(r'<CurrentTreble>(-?\d+)</CurrentTreble>', resp)
        return int(m.group(1)) if m else None

    async def set_treble(self, treble):
        treble = max(-10, min(10, treble))
        body = (
            '<u:SetTreble xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><DesiredTreble>{}</DesiredTreble>'
            '</u:SetTreble>'
        ).format(treble)
        resp = await self.soap_request('RenderingControl', 'SetTreble', body)
        return resp is not None

    async def get_loudness(self):
        body = (
            '<u:GetLoudness xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><Channel>Master</Channel>'
            '</u:GetLoudness>'
        )
        resp = await self.soap_request('RenderingControl', 'GetLoudness', body)
        if resp is None:
            return None
        m = re.search(r'<CurrentLoudness>(\d)</CurrentLoudness>', resp)
        return bool(int(m.group(1))) if m else None

    async def set_loudness(self, enabled):
        body = (
            '<u:SetLoudness xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><Channel>Master</Channel>'
            '<DesiredLoudness>{}</DesiredLoudness>'
            '</u:SetLoudness>'
        ).format(1 if enabled else 0)
        resp = await self.soap_request('RenderingControl', 'SetLoudness', body)
        return resp is not None

    async def get_night_mode(self):
        """Nachtmodus: 1=Ein, 0=Aus, -1=Nicht unterstützt"""
        body = (
            '<u:GetEQ xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><EQType>NightMode</EQType>'
            '</u:GetEQ>'
        )
        resp = await self.soap_request('RenderingControl', 'GetEQ', body)
        if resp is None:
            return -1
        m = re.search(r'<CurrentValue>(\d+)</CurrentValue>', resp)
        return int(m.group(1)) if m else -1

    async def set_night_mode(self, enabled):
        body = (
            '<u:SetEQ xmlns:u="urn:schemas-upnp-org:service:RenderingControl:1">'
            '<InstanceID>0</InstanceID><EQType>NightMode</EQType>'
            '<DesiredValue>{}</DesiredValue>'
            '</u:SetEQ>'
        ).format(1 if enabled else 0)
        resp = await self.soap_request('RenderingControl', 'SetEQ', body)
        return resp is not None and 'SetEQResponse' in (resp or '')

    # ============ ZoneGroupTopology ============

    async def get_zone_group_attributes(self):
        body = (
            '<u:GetZoneGroupAttributes '
            'xmlns:u="urn:schemas-upnp-org:service:ZoneGroupTopology:1">'
            '</u:GetZoneGroupAttributes>'
        )
        resp = await self.soap_request('ZoneGroupTopology', 'GetZoneGroupAttributes', body)
        if resp is None:
            return {}

        result = {}
        for tag in ['CurrentZoneGroupName', 'CurrentZoneGroupID',
                     'CurrentZonePlayerUUIDsInGroup']:
            m = re.search(r'<{0}>(.*?)</{0}>'.format(tag), resp, re.DOTALL)
            if m:
                result[tag] = m.group(1)
        return result

    # ============ ContentDirectory (Favoriten) ============

    async def browse_favorites(self):
        """Holt Sonos Favoriten via Browse(FV:2)"""
        body = (
            '<u:Browse xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1">'
            '<ObjectID>FV:2</ObjectID>'
            '<BrowseFlag>BrowseDirectChildren</BrowseFlag>'
            '<Filter>*</Filter>'
            '<StartingIndex>0</StartingIndex>'
            '<RequestedCount>100</RequestedCount>'
            '<SortCriteria></SortCriteria>'
            '</u:Browse>'
        )
        resp = await self.soap_request('ContentDirectory', 'Browse', body, timeout=10)
        if resp is None:
            return []

        m = re.search(r'<Result>(.*?)</Result>', resp, re.DOTALL)
        if not m:
            return []

        didl = html_unescape(m.group(1))
        items = re.findall(r'<item[^>]*>.*?</item>', didl, re.DOTALL)

        favorites = []
        for item in items:
            fav = {}
            tm = re.search(r'<dc:title>([^<]*)</dc:title>', item)
            if tm:
                fav['name'] = html_unescape(tm.group(1))
            else:
                continue

            um = re.search(r'<res[^>]*>([^<]*)</res>', item)
            if um:
                fav['uri'] = html_unescape(um.group(1))

            am = re.search(r'<upnp:albumArtURI>([^<]*)</upnp:albumArtURI>', item)
            if am:
                fav['logo'] = html_unescape(am.group(1))
            elif 'uri' in fav and 'x-sonosapi-stream:' in fav['uri']:
                sid = re.search(r'x-sonosapi-stream:([^?]+)', fav['uri'])
                if sid:
                    fav['logo'] = "https://cdn-profiles.tunein.com/{}/images/logod.jpg".format(sid.group(1))

            mm = re.search(r'<r:resMD>(.+?)</r:resMD>', item, re.DOTALL)
            if mm:
                fav['meta'] = mm.group(1)

            favorites.append(fav)

        return favorites

    # ============ Verbindungsprüfung ============

    async def check_connection(self):
        """Prüft ob Sonos erreichbar ist (HTTP GET auf Port 1400)"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._base_url + '/xml/device_description.xml',
                    timeout=aiohttp.ClientTimeout(total=CONNECTION_TIMEOUT)
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False


# ============================================================================
# SONOS CONTROLLER LOGICBLOCK
# ============================================================================

class SonosController(LogicBlock):
    """SONOS Controller via lokale UPnP/SOAP-API"""

    ID = 20035
    NAME = "SONOS Controller"
    DESCRIPTION = "Steuert und überwacht Sonos über lokale UPnP/SOAP-API"
    VERSION = "1.4"
    AUTHOR = "Reinhard Socha"
    CATEGORY = "Audio"
    REMANENT = True

    HELP = """Funktionsweise:
Steuert einen Sonos-Lautsprecher über die lokale UPnP/SOAP-API (Port 1400).
E1 aktiviert den Baustein, E3 enthält die IP-Adresse des Lautsprechers.
Im Intervall (E2, Standard 1s) werden Status, Titel, Cover etc. abgefragt.

Steuerung:
- E4/E5/E6: Play/Pause/Stop (werden bei jedem Wert ausgelöst)
- E7/E8: Next/Previous Track
- E9: Volume (0-100), E15: Mute (0/1)
- E10-E14: Loudness, Bass, Treble, Playmode, Crossfade
- E16: Play URI – spielt Radio-Stream, Spotify-URI oder Sonos-Favorit ab
- E18: TTS-Ansage mit automatischer Zustandswiederherstellung
- E21: Nachtmodus für Soundbar/Beam/Arc

Ausgänge:
- A1-A6: Name, Status (1=Play, 2=Pause, 3=Stop), Radiosender, Titel, Artist, Album
- A7: Cover-URL, A13: Aktuelle URI, A30: Streaming-Dienst
- A15-A21: Volume, Bass, Treble, Loudness, Crossfade, Mute, Playmode
- A31: Genre (iTunes-Lookup), A32-A35: Genre-Farben für Lichtsteuerung

Remanent:
Einstellungen (IP, Volume, Bass, Treble, etc.) werden über Reboots gespeichert.
Play/Pause/Stop werden NICHT gespeichert – der Sonos spielt eigenständig weiter.

Versionshistorie:
v1.4 – Remanenz: Settings + Ausgabewerte überleben Reboots
v1.3 – TRIGGER_ALWAYS für Play/Pause/Stop, force_trigger Fix
v1.2 – Genre-Farben, iTunes-Lookup, Streaming-Dienst-Erkennung
v1.1 – Favoriten-Cache, Gruppen-Erkennung, Reconnect mit Backoff
v1.0 – Erstversion: Play/Pause/Stop, Volume, Radio, TTS"""

    INPUTS = {
        'E1':  {'name': 'Start/Stop', 'type': 'bool', 'default': True},
        'E2':  {'name': 'Intervall (s)', 'type': 'int', 'default': 1},
        'E3':  {'name': 'IP-Adresse', 'type': 'str', 'default': '192.168.0.15'},
        'E4':  {'name': 'Play', 'type': 'bool', 'default': ''},
        'E5':  {'name': 'Pause', 'type': 'bool', 'default': False},
        'E6':  {'name': 'Stop', 'type': 'bool', 'default': ''},
        'E7':  {'name': 'Next', 'type': 'bool', 'default': False},
        'E8':  {'name': 'Previous', 'type': 'bool', 'default': False},
        'E9':  {'name': 'Volume', 'type': 'int', 'default': -1},
        'E10': {'name': 'Loudness', 'type': 'int', 'default': -1},
        'E11': {'name': 'Bass', 'type': 'int', 'default': -100},
        'E12': {'name': 'Treble', 'type': 'int', 'default': -100},
        'E13': {'name': 'Playmode', 'type': 'int', 'default': -1},
        'E14': {'name': 'Crossfade', 'type': 'int', 'default': -1},
        'E15': {'name': 'Mute', 'type': 'int', 'default': -1},
        'E16': {'name': 'Play URI', 'type': 'str', 'default': ''},
        'E17': {'name': 'Reserve', 'type': 'str', 'default': ''},
        'E18': {'name': 'Ansagen', 'type': 'str', 'default': ''},
        'E19': {'name': 'Ansage Volume', 'type': 'int', 'default': 20},
        'E20': {'name': 'Lichtsteuerung', 'type': 'bool', 'default': True},
        'E21': {'name': 'Nachtmodus', 'type': 'int', 'default': -1},
        'E22': {'name': 'Debug', 'type': 'bool', 'default': False},
    }

    OUTPUTS = {
        'A1':  {'name': 'Name', 'type': 'str'},
        'A2':  {'name': 'Status', 'type': 'int'},
        'A3':  {'name': 'Radiosender', 'type': 'str'},
        'A4':  {'name': 'Titel', 'type': 'str'},
        'A5':  {'name': 'Artist', 'type': 'str'},
        'A6':  {'name': 'Album', 'type': 'str'},
        'A7':  {'name': 'Cover URL', 'type': 'str'},
        'A8':  {'name': 'RealTime', 'type': 'str'},
        'A9':  {'name': 'Duration', 'type': 'str'},
        'A10': {'name': 'Track Position', 'type': 'int'},
        'A11': {'name': 'Count Track', 'type': 'int'},
        'A12': {'name': 'Track Nr.', 'type': 'int'},
        'A13': {'name': 'CurrentURI', 'type': 'str'},
        'A14': {'name': 'Online Status', 'type': 'bool'},
        'A15': {'name': 'Volume', 'type': 'int'},
        'A16': {'name': 'Bass', 'type': 'int'},
        'A17': {'name': 'Treble', 'type': 'int'},
        'A18': {'name': 'Loudness', 'type': 'int'},
        'A19': {'name': 'Crossfade', 'type': 'int'},
        'A20': {'name': 'Mute', 'type': 'int'},
        'A21': {'name': 'Playmode', 'type': 'int'},
        'A22': {'name': 'Nachtmodus', 'type': 'str'},
        'A23': {'name': 'Gruppenrolle', 'type': 'str'},
        'A24': {'name': 'Reconnect Count', 'type': 'int'},
        'A25': {'name': 'Last Error', 'type': 'str'},
        'A26': {'name': 'Favoriten Name (join)', 'type': 'str'},
        'A27': {'name': 'Favoriten Uri (join)', 'type': 'str'},
        'A28': {'name': 'Favoriten Cover (join)', 'type': 'str'},
        'A29': {'name': 'Gruppenmitglieder (join)', 'type': 'str'},
        'A30': {'name': 'Streaming Dienst', 'type': 'str'},
        'A31': {'name': 'Genre', 'type': 'str'},
        'A32': {'name': 'Farbe 1 RGB', 'type': 'str'},
        'A33': {'name': 'Farbe 1 HEX', 'type': 'str'},
        'A34': {'name': 'Farbe 2 RGB', 'type': 'str'},
        'A35': {'name': 'Farbe 2 HEX', 'type': 'str'},
    }

    # Timing-Konstanten (Sekunden)
    SLEEP_AFTER_COMMAND = 0.5
    SLEEP_AFTER_PLAY = 0.3
    SLEEP_MEDIA_UPDATE = 0.5

    # Eingänge die IMMER triggern (auch bei gleichem Wert), wie in PHP 'refresh'
    # E4=Play, E5=Pause, E6=Stop: sollen IMMER den Befehl senden, egal welcher Wert
    TRIGGER_ALWAYS_INPUTS = {'E4', 'E5', 'E6', 'E7', 'E8', 'E16', 'E18'}

    def set_input(self, key, value, force_trigger=False):
        """Override: Trigger-Inputs lösen IMMER aus (auch bei gleichem Wert)"""
        if key in self.TRIGGER_ALWAYS_INPUTS:
            # Type conversion wie in Base
            input_type = self.INPUTS.get(key, {}).get('type', 'str')
            try:
                if input_type == 'bool':
                    if isinstance(value, str):
                        value = value.lower() in ('1', 'true', 'on', 'ein')
                    else:
                        value = bool(value)
                elif input_type == 'int':
                    value = int(float(value)) if value is not None else 0
                elif input_type == 'str':
                    value = str(value) if value is not None else ''
            except (ValueError, TypeError):
                pass
            self._input_values[key] = value
            # Immer triggern - unabhängig vom Wert
            if self._enabled:
                self._trigger_execute(key)
            return True
        return super().set_input(key, value, force_trigger)

    def on_start(self):
        super().on_start()
        self._soap = None
        self._is_online = False
        self._reconnect_count = 0
        self._consecutive_offline = 0
        self._tick = 0
        self._pending_command = None
        self._itunes_cache = {}
        self._favorites_cache = None
        self._favorites_ts = 0
        self._last_transport = 3
        self._last_uri = ''
        self._last_radio_title = ''
        self._last_stream_content = ''
        self._last_title = ''
        self._last_artist = ''
        self._is_radio = False
        self._is_tts_playing = False

        # Farbanimation
        self._color1 = [255, 200, 150]
        self._color2 = [245, 222, 179]
        self._target1 = [255, 200, 150]
        self._target2 = [245, 222, 179]
        self._palette_index = 0
        self._current_palette = get_genre_palette('default')

        interval = self.get_input('E2') or 1
        if interval < 1:
            interval = 1
        self.set_timer(interval)
        logger.info("[{}] SONOS Controller gestartet, Intervall: {}s".format(self.ID, interval))

    # ---- Remanenz: Einstellungen über Reboots speichern ----
    # NICHT gespeichert: E4-E8 (Play/Pause/Stop/Next/Previous) – das sind Kommandos, keine Settings

    # Inputs die als Einstellungen gespeichert werden (keine Befehle)
    _REMANENT_INPUTS = {'E1', 'E2', 'E3', 'E9', 'E10', 'E11', 'E12', 'E13', 'E14', 'E15',
                        'E16', 'E17', 'E18', 'E19', 'E20', 'E21', 'E22'}

    def get_remanent_state(self):
        """Speichere Settings + letzte Ausgabewerte für Reboot-Persistenz"""
        saved_inputs = {k: v for k, v in self._input_values.items() if k in self._REMANENT_INPUTS}
        saved_outputs = dict(self._output_values)
        return {
            'inputs': saved_inputs,
            'outputs': saved_outputs,
        }

    def restore_remanent_state(self, state):
        """Stelle Settings nach Reboot wieder her"""
        if not state:
            return

        # Restore input settings
        for key, value in state.get('inputs', {}).items():
            if key in self.INPUTS and key in self._REMANENT_INPUTS:
                self._input_values[key] = value

        # Restore last known output values (dashboard shows something useful)
        for key, value in state.get('outputs', {}).items():
            if key in self.OUTPUTS:
                self._output_values[key] = value

        self.debug('Status', 'Settings wiederhergestellt')
        logger.info(f"{self.instance_id}: Remanent-Settings wiederhergestellt")

    def execute(self, triggered_by=None):
        if not self.get_input('E1'):
            return

        # Intervall-Änderung
        if triggered_by == 'E2':
            interval = self.get_input('E2') or 1
            if interval < 1:
                interval = 1
            self.set_timer(interval)
            return

        # IP-Änderung -> SOAP-Client neu erstellen
        if triggered_by == 'E3':
            ip = (self.get_input('E3') or '').strip()
            if ip:
                self._soap = SonosSoap(ip)
                self._is_online = False
            return

        # Steuer-Befehle
        command_map = {
            'E4': 'play', 'E5': 'pause', 'E6': 'stop',
            'E7': 'next', 'E8': 'previous',
            'E9': 'volume', 'E10': 'loudness',
            'E11': 'bass', 'E12': 'treble',
            'E13': 'playmode', 'E14': 'crossfade', 'E15': 'mute',
            'E16': 'radio', 'E18': 'tts', 'E21': 'nightmode',
        }

        if triggered_by in command_map:
            # Play/Pause/Stop/Next/Previous: Immer ausführen (TRIGGER_ALWAYS_INPUTS)
            # Kein Wert-Check nötig - set_input Override triggert immer

            self._pending_command = command_map[triggered_by]
            asyncio.create_task(self._process_command())

    async def on_timer(self):
        if not self.get_input('E1'):
            return

        ip = (self.get_input('E3') or '').strip()
        if not ip:
            self.set_output('A25', 'Keine IP-Adresse')
            self.set_output('A14', False)
            return

        # SOAP-Client erstellen falls nötig
        if self._soap is None:
            self._soap = SonosSoap(ip)

        self._tick += 1

        # Verbindungsprüfung (alle 5 Ticks oder wenn offline)
        if (self._tick % 5) == 0 or not self._is_online:
            online = await self._soap.check_connection()
            if not online:
                if not self._is_online:
                    self._consecutive_offline += 1
                self._set_online(False)
                self.set_output('A25', 'Verbindung fehlgeschlagen')
                return
            else:
                if not self._is_online:
                    self._consecutive_offline = 0
                    self._reconnect_count += 1
                    self.set_output('A24', self._reconnect_count)
                    logger.info("[{}] Reconnect erfolgreich".format(self.ID))
                self._set_online(True)

        if not self._is_online:
            return

        # Transport-Status - IMMER setzen wenn A2 leer/None ist
        transport = await self._soap.get_transport_info()
        if transport is not None:
            current_a2 = self.get_output('A2')
            if transport != self._last_transport or current_a2 is None or current_a2 == '' or current_a2 == ' ':
                self.set_output('A2', transport)
                self._last_transport = transport

        # Fast Outputs (Volume, Mute) - jeder Tick
        await self._update_outputs_fast()

        # Slow Outputs (Bass, Treble, etc.) - alle 5 Ticks
        if (self._tick % 5) == 0:
            await self._update_outputs_slow()

        # Listen (Favoriten, Gruppen) - alle 60 Ticks
        if (self._tick % 60) == 0:
            await self._update_lists()

        # Media Info - bei Play immer, sonst alle 10 Ticks
        if transport == 1 or (self._tick % 10) == 0:
            await self._update_media_info(transport or 3)

        # Farbanimation
        if self.get_input('E20'):
            self._animate_colors()

    # ============ BEFEHLE ============

    async def _process_command(self):
        """Verarbeitet den anstehenden Befehl"""
        command = self._pending_command
        self._pending_command = None
        debug = self.get_input('E22')

        if not self._soap:
            return

        if debug:
            logger.info("[{}] CMD: {}".format(self.ID, command))

        try:
            if command == 'play':
                await self._soap.play()
                await asyncio.sleep(self.SLEEP_AFTER_COMMAND)
                self.set_output('A2', 1)
                self._last_transport = 1
            elif command == 'pause':
                await self._soap.pause()
                await asyncio.sleep(self.SLEEP_AFTER_COMMAND)
                self.set_output('A2', 2)
                self._last_transport = 2
            elif command == 'stop':
                await self._soap.stop()
                await asyncio.sleep(self.SLEEP_AFTER_COMMAND)
                self.set_output('A2', 3)
                self._last_transport = 3
            elif command == 'next':
                await self._soap.next()
            elif command == 'previous':
                await self._soap.previous()
            elif command == 'volume':
                vol = max(0, min(100, self.get_input('E9') or 0))
                await self._soap.set_volume(vol)
            elif command == 'bass':
                bass = max(-10, min(10, self.get_input('E11') or 0))
                await self._soap.set_bass(bass)
            elif command == 'treble':
                treble = max(-10, min(10, self.get_input('E12') or 0))
                await self._soap.set_treble(treble)
            elif command == 'loudness':
                await self._soap.set_loudness(bool(self.get_input('E10')))
            elif command == 'playmode':
                mode = max(0, min(3, self.get_input('E13') or 0))
                await self._soap.set_play_mode(mode)
            elif command == 'crossfade':
                await self._soap.set_crossfade_mode(bool(self.get_input('E14')))
            elif command == 'mute':
                await self._soap.set_mute(bool(self.get_input('E15')))
            elif command == 'radio':
                await self._play_uri(self.get_input('E16') or '')
            elif command == 'tts':
                await self._play_tts()
            elif command == 'nightmode':
                val = self.get_input('E21')
                if val is not None and val >= 0:
                    success = await self._soap.set_night_mode(bool(val))
                    if success:
                        self.set_output('A22', str(1 if val else 0))

            # Nach Befehl kurz warten und Status aktualisieren
            await asyncio.sleep(self.SLEEP_AFTER_COMMAND)

        except Exception as e:
            logger.error("[{}] Command error: {}".format(self.ID, e))
            self.set_output('A25', str(e)[:100])

    async def _play_uri(self, uri):
        """Spielt verschiedene URI-Typen ab"""
        uri = uri.strip()
        if not uri:
            return

        debug = self.get_input('E22')
        if debug:
            logger.info("[{}] PLAY_URI: '{}'".format(self.ID, uri))

        if 'x-rincon-cpcontainer' in uri:
            await self._play_streaming_container(uri)
        elif is_radio_uri(uri):
            # TuneIn/Radio-Streams: set_radio mit Metadaten
            await self._soap.set_radio(uri)
            await asyncio.sleep(self.SLEEP_AFTER_COMMAND)
            await self._soap.play()
        elif uri.startswith('http://') or uri.startswith('https://'):
            # Generische HTTP/HTTPS URIs: direkt als Transport-URI setzen
            await self._soap.set_av_transport_uri(uri, '')
            await asyncio.sleep(self.SLEEP_AFTER_COMMAND)
            await self._soap.play()
        elif 'x-file-cifs' in uri or 'x-sonos-spotify' in uri:
            zone = await self._soap.get_zone_group_attributes()
            uuid = zone.get('CurrentZonePlayerUUIDsInGroup', '')
            if uuid:
                uuid = uuid.split(',')[0]
                await self._soap.clear_queue()
                await asyncio.sleep(0.2)
                await self._soap.add_to_queue(uri)
                await self._soap.set_av_transport_uri('x-rincon-queue:{}#0'.format(uuid))
                await self._soap.play()
        else:
            # Fallback: als Radio/Stream behandeln
            await self._soap.set_av_transport_uri(uri, '')
            await asyncio.sleep(self.SLEEP_AFTER_COMMAND)
            await self._soap.play()

    async def _play_streaming_container(self, uri):
        """Spielt Streaming-Container (Spotify, Amazon, Apple Music) ab"""
        meta = ''
        if self._favorites_cache:
            from urllib.parse import unquote
            search_uri = uri.strip()
            search_decoded = unquote(search_uri)
            for fav in self._favorites_cache:
                fav_uri = fav.get('uri', '').strip()
                if fav_uri == search_uri or unquote(fav_uri) == search_decoded:
                    meta = fav.get('meta', '')
                    break

        if meta:
            decoded_meta = html_unescape(html_unescape(meta))
            zone = await self._soap.get_zone_group_attributes()
            uuid = zone.get('CurrentZonePlayerUUIDsInGroup', '')
            if uuid:
                uuid = uuid.split(',')[0]
                await self._soap.clear_queue()
                await asyncio.sleep(0.2)
                await self._soap.add_to_queue(uri, html_escape(decoded_meta))
                await self._soap.set_av_transport_uri('x-rincon-queue:{}#0'.format(uuid))
                await asyncio.sleep(self.SLEEP_AFTER_PLAY)
                await self._soap.play()
        else:
            logger.warning("[{}] Streaming-Container ohne Metadaten".format(self.ID))
            self.set_output('A25', 'Container: Keine Metadaten')

    async def _play_tts(self):
        """TTS-Ansage abspielen und danach vorherigen Zustand wiederherstellen
        
        Portiert von PHP playTTS() - nutzt Queue ohne zu leeren:
        1. Status sichern
        2. TTS zur Queue hinzufügen (NICHT leeren!)
        3. Queue-Position ermitteln und Track setzen
        4. Nach Abspielen: TTS-Track aus Queue entfernen
        5. Originalzustand wiederherstellen
        """
        # Guard: verhindert doppelte Ausführung
        if self._is_tts_playing:
            logger.info("[{}] TTS Guard: bereits aktiv, ignoriere".format(self.ID))
            return

        uri = (self.get_input('E18') or '').strip()
        if not uri:
            return

        self._is_tts_playing = True
        debug = self.get_input('E22')

        try:
            tts_vol = max(0, min(100, self.get_input('E19') or 20))

            if debug:
                logger.info("[{}] TTS Start: uri='{}', vol={}".format(self.ID, uri, tts_vol))

            # ===== Zustand sichern (wie PHP) =====
            saved_transport = await self._soap.get_transport_info()
            saved_volume = await self._soap.get_volume()
            saved_media = await self._soap.get_media_info()
            saved_position = await self._soap.get_position_info()
            saved_play_mode = await self._soap.get_transport_settings()
            saved_zone = await self._soap.get_zone_group_attributes()

            saved_uri = saved_media.get('CurrentURI', '')
            saved_title = saved_media.get('title', '')
            was_playing = (saved_transport == 1)

            if debug:
                logger.info("[{}] TTS Saved: transport={}, uri='{}', title='{}'".format(
                    self.ID, saved_transport, saved_uri[:80] if saved_uri else '', saved_title))

            # ===== UUID prüfen =====
            uuid = saved_zone.get('CurrentZonePlayerUUIDsInGroup', '')
            if not uuid:
                logger.error("[{}] TTS: Keine Zone-Info verfügbar".format(self.ID))
                return
            uuid = uuid.split(',')[0]

            # ===== Pausieren falls nötig =====
            if was_playing:
                await self._soap.pause()
                await asyncio.sleep(0.3)

            # ===== URI ermitteln =====
            if uri.startswith('//'):
                tts_uri = 'x-file-cifs:' + uri
            elif uri.startswith('http://') or uri.startswith('https://'):
                tts_uri = uri
            else:
                logger.error("[{}] TTS: Ungültiges URI-Format: {}".format(self.ID, uri))
                return

            # ===== TTS zur Queue hinzufügen (NICHT leeren wie PHP!) =====
            await self._soap.set_volume(tts_vol)
            await self._soap.add_to_queue(tts_uri)
            await self._soap.set_av_transport_uri('x-rincon-queue:{}#0'.format(uuid))

            # Queue-Position ermitteln (TTS ist der letzte Track)
            playlist_count = await self._soap.get_current_playlist()
            message_pos = max(1, playlist_count)

            await self._soap.set_mute(False)
            await self._soap.set_play_mode(0)
            await self._soap.set_track(message_pos)
            await asyncio.sleep(0.5)
            await self._soap.play()

            # ===== Warten bis TTS fertig (mit Timeout wie PHP: max 24s) =====
            await asyncio.sleep(1.5)
            for _ in range(120):  # 120 * 0.2s = 24s max
                state = await self._soap.get_transport_info()
                if state is None or state != 1:
                    break
                await asyncio.sleep(0.2)

            # ===== TTS-Track aus Queue entfernen (wie PHP RemoveFromQueue) =====
            try:
                await self._soap.remove_from_queue(message_pos)
            except Exception as e:
                logger.warning("[{}] RemoveFromQueue fehlgeschlagen: {}".format(self.ID, e))

            # ===== Zustand wiederherstellen (wie PHP) =====
            if saved_volume is not None:
                await self._soap.set_volume(saved_volume)

            if saved_play_mode is not None and saved_play_mode != 0:
                await self._soap.set_play_mode(saved_play_mode)

            # Originalquelle wiederherstellen
            if saved_title:
                # Radio: über TrackURI wiederherstellen (wie PHP)
                track_uri = saved_position.get('TrackURI', '')
                if track_uri:
                    await self._soap.set_radio(track_uri, saved_title)
            elif saved_position.get('TrackURI'):
                # Playlist: Queue wiederherstellen
                await self._soap.set_av_transport_uri('x-rincon-queue:{}#0'.format(uuid))
                if saved_position.get('Track'):
                    await self._soap.set_track(int(saved_position['Track']))

            # Wieder abspielen wenn vorher lief
            if was_playing:
                await asyncio.sleep(0.3)
                await self._soap.play()

            if debug:
                logger.info("[{}] TTS Ende: Zustand wiederhergestellt".format(self.ID))

        except Exception as e:
            logger.error("[{}] TTS Fehler: {}".format(self.ID, e))
            self.set_output('A25', 'TTS Fehler: {}'.format(str(e)[:80]))
        finally:
            self._is_tts_playing = False

    # ============ OUTPUT UPDATES ============

    def _set_online(self, online):
        self._is_online = online
        self.set_output('A14', online)
        if online:
            self.set_output('A25', '')

    async def _update_outputs_fast(self):
        """Volume und Mute (jeden Tick)"""
        volume = await self._soap.get_volume()
        if volume is not None:
            self.set_output('A15', volume)

        mute = await self._soap.get_mute()
        if mute is not None:
            self.set_output('A20', 1 if mute else 0)

    async def _update_outputs_slow(self):
        """Bass, Treble, Loudness, Playmode, Crossfade, Gruppen, Nachtmodus"""
        bass = await self._soap.get_bass()
        if bass is not None:
            self.set_output('A16', bass)

        treble = await self._soap.get_treble()
        if treble is not None:
            self.set_output('A17', treble)

        loudness = await self._soap.get_loudness()
        if loudness is not None:
            self.set_output('A18', 1 if loudness else 0)

        playmode = await self._soap.get_transport_settings()
        if playmode is not None:
            self.set_output('A21', playmode)

        crossfade = await self._soap.get_crossfade_mode()
        if crossfade is not None:
            self.set_output('A19', 1 if crossfade else 0)

        # Gruppenrolle
        zone_info = await self._soap.get_zone_group_attributes()
        media_info = await self._soap.get_media_info()

        role = determine_group_role(zone_info, media_info)
        self.set_output('A23', role)

        members = get_group_members(zone_info)
        self.set_output('A29', members)

        # Streaming-Dienst
        uri = media_info.get('CurrentURI', '')
        service = detect_streaming_service(uri)
        self.set_output('A30', service)

        # Nachtmodus
        night = await self._soap.get_night_mode()
        if night >= 0:
            self.set_output('A22', str(night))
        else:
            self.set_output('A22', ' ')

        # Name
        zone_name = zone_info.get('CurrentZoneGroupName', '')
        if ' + ' in zone_name:
            zone_name = zone_name.split(' + ')[0]
        if zone_name:
            self.set_output('A1', zone_name)

    async def _update_lists(self):
        """Favoriten und Gruppen (selten)"""
        import time
        now = time.time()

        # Favoriten-Cache (5 Min TTL)
        if now - self._favorites_ts > 300 or self._favorites_cache is None:
            favorites = await self._soap.browse_favorites()
            if favorites:
                self._favorites_cache = favorites
                self._favorites_ts = now

                names = '|'.join(f.get('name', '') for f in favorites)
                uris = '|'.join(f.get('uri', '') for f in favorites)
                logos = '|'.join(f.get('logo', '') for f in favorites)
                self.set_output('A26', names)
                self.set_output('A27', uris)
                self.set_output('A28', logos)

    async def _update_media_info(self, transport):
        """Media-Informationen aktualisieren"""
        if transport != 1:
            self.set_output('A3', ' ')
            self.set_output('A4', ' ')
            self.set_output('A5', ' ')
            self.set_output('A8', ' ')
            self.set_output('A31', ' ')
            self._set_target_colors(get_genre_palette('default'))
            return

        media_info = await self._soap.get_media_info()
        pos_info = await self._soap.get_position_info()

        current_uri = media_info.get('CurrentURI', '')
        radio_title = media_info.get('title', '')

        # Radio-Modus Erkennung
        is_radio = bool(radio_title) or is_radio_uri(current_uri)

        if is_radio:
            if radio_title:
                self.set_output('A3', radio_title)
                self._last_radio_title = radio_title

            stream = pos_info.get('streamContent', '')
            if stream and stream != self._last_stream_content:
                self._last_stream_content = stream
                parsed = parse_stream_content(stream)

                if parsed['artist'] and parsed['title']:
                    self.set_output('A4', parsed['title'])
                    self.set_output('A5', parsed['artist'])

                    itunes = await get_itunes_info(
                        parsed['artist'], parsed['title'], self._itunes_cache
                    )
                    if itunes:
                        if itunes.get('cover'):
                            self.set_output('A7', itunes['cover'])
                        if itunes.get('genre'):
                            self.set_output('A31', itunes['genre'])
                            self._set_target_colors(get_genre_palette(itunes['genre']))
                else:
                    self.set_output('A4', stream)
                    self.set_output('A5', ' ')

            self.set_output('A10', 0)
            self.set_output('A11', ' ')
            self.set_output('A12', ' ')

        else:
            duration = pos_info.get('TrackDuration', '')
            if duration and duration != '0:00:00':
                title = pos_info.get('title', '')
                artist = pos_info.get('artist', '')
                album = pos_info.get('album', '')

                if title != self._last_title or artist != self._last_artist:
                    self._last_title = title
                    self._last_artist = artist
                    self.set_output('A4', title or ' ')
                    self.set_output('A5', artist or ' ')

                    if artist and title:
                        itunes = await get_itunes_info(artist, title, self._itunes_cache)
                        if itunes and itunes.get('genre'):
                            self.set_output('A31', itunes['genre'])
                            self._set_target_colors(get_genre_palette(itunes['genre']))
                        else:
                            self.set_output('A31', ' ')
                            self._set_target_colors(get_genre_palette('default'))

                self.set_output('A6', album or ' ')

                cover = pos_info.get('albumArtURI', '')
                if cover:
                    self.set_output('A7', cover)

                track_nr = pos_info.get('Track', '')
                if track_nr:
                    self.set_output('A12', int(track_nr))

                self.set_output('A9', duration)
                rel_time = pos_info.get('RelTime', '')
                if rel_time:
                    self.set_output('A8', rel_time)
                    self.set_output('A10', calculate_track_percent(rel_time, duration))

        if current_uri:
            self.set_output('A13', current_uri)

        self.set_output('A25', '')

    # ============ FARBANIMATION ============

    def _set_target_colors(self, palette):
        """Setzt neue Zielfarben aus der Palette"""
        self._current_palette = palette
        self._palette_index = 0
        self._target1 = list(palette[0])
        self._target2 = list(palette[1])

    def _animate_colors(self, step=15):
        """Weiche Farbübergänge (wird jeden Tick aufgerufen)"""
        changed = False

        for i in range(3):
            new_val = move_towards(self._color1[i], self._target1[i], step)
            if new_val != self._color1[i]:
                self._color1[i] = new_val
                changed = True

        for i in range(3):
            new_val = move_towards(self._color2[i], self._target2[i], step)
            if new_val != self._color2[i]:
                self._color2[i] = new_val
                changed = True

        if (self._color1 == self._target1 and self._color2 == self._target2):
            self._palette_index = (self._palette_index + 1) % 5
            next_idx = self._palette_index
            next_idx2 = (next_idx + 1) % 5
            self._target1 = list(self._current_palette[next_idx])
            self._target2 = list(self._current_palette[next_idx2])

        if changed:
            r1, g1, b1 = self._color1
            r2, g2, b2 = self._color2
            self.set_output('A32', rgb_to_str(r1, g1, b1))
            self.set_output('A33', rgb_to_hex(r1, g1, b1))
            self.set_output('A34', rgb_to_str(r2, g2, b2))
            self.set_output('A35', rgb_to_hex(r2, g2, b2))

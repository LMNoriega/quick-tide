#!/usr/bin/env python3
"""
Tidal Backend Module for Serpantinum Shell Integration.
Reuses existing low-tide session, credentials and tidalapi client.
"""

from __future__ import annotations

import os
import sys
import json
import logging
import urllib.request
import urllib.parse
import re
import threading
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

# Ensure low-tide virtualenv and modules are on sys.path
import glob
LOWTIDE_DIR = os.path.expanduser("~/.local/share/low-tide")
venv_site_pkgs = glob.glob(os.path.join(LOWTIDE_DIR, ".venv", "lib", "python*", "site-packages"))

for p in [LOWTIDE_DIR] + venv_site_pkgs:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

try:
    from lowtide.tidal_client import TidalClient
    from lowtide.lyrics import parse_lrc, LyricLine
except ImportError as e:
    raise RuntimeError(f"No se pudo cargar lowtide desde {LOWTIDE_DIR}: {e}")

log = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".cache" / "tidal-gui" / "covers"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_client_lock = threading.Lock()
_client_instance: Optional[TidalClient] = None


def get_client() -> TidalClient:
    global _client_instance
    with _client_lock:
        if _client_instance is None:
            _client_instance = TidalClient()
        return _client_instance


def format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "0:00"
    s = int(seconds)
    mins = s // 60
    secs = s % 60
    return f"{mins}:{secs:02d}"


def download_cover(url: str | None, key: str | int) -> str:
    """Download cover image to cache and return local file path."""
    if not url:
        return ""
    local_path = CACHE_DIR / f"{key}.jpg"
    if local_path.is_file() and local_path.stat().st_size > 0:
        return str(local_path)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp, open(local_path, "wb") as f:
            f.write(resp.read())
        return str(local_path)
    except Exception as e:
        log.warning("Error descargando carátula %s: %s", url, e)
        return ""


def search_tracks(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    client = get_client()
    try:
        raw = client.search(query, limit=limit)
        tracks = raw.get("tracks", [])
    except Exception as e:
        log.error("Error buscando canciones: %s", e)
        return []

    results = []
    for t in tracks:
        album_name = getattr(getattr(t, "album", None), "name", "")
        artist_name = getattr(getattr(t, "artist", None), "name", "Artista desconocido")
        cover_url = ""
        try:
            if hasattr(t, "album") and t.album:
                cover_url = t.album.image(640)
        except Exception:
            pass

        quality = getattr(t, "audio_quality", "LOSSLESS")
        results.append({
            "id": t.id,
            "type": "track",
            "name": t.name,
            "artist": artist_name,
            "album": album_name,
            "duration": t.duration,
            "duration_str": format_duration(t.duration),
            "cover_url": cover_url,
            "quality": str(quality).replace("AudioQuality.", ""),
            "explicit": bool(getattr(t, "explicit", False)),
        })
    return results


def search_albums(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    client = get_client()
    try:
        raw = client.search(query, limit=limit)
        albums = raw.get("albums", [])
    except Exception as e:
        log.error("Error buscando álbumes: %s", e)
        return []

    results = []
    for a in albums:
        artist_name = getattr(getattr(a, "artist", None), "name", "Artista desconocido")
        cover_url = ""
        try:
            if hasattr(a, "image"):
                cover_url = a.image(640)
        except Exception:
            pass

        num_tracks = getattr(a, "num_tracks", 0)
        release_date = getattr(a, "release_date", None)
        year = str(release_date.year) if release_date else ""

        results.append({
            "id": a.id,
            "type": "album",
            "name": a.name,
            "artist": artist_name,
            "num_tracks": num_tracks,
            "year": year,
            "cover_url": cover_url,
        })
    return results


def get_track_details(track_id: int) -> Optional[Dict[str, Any]]:
    client = get_client()
    try:
        t = client.get_track(track_id)
        if not t:
            return None
        album_name = getattr(getattr(t, "album", None), "name", "")
        album_id = getattr(getattr(t, "album", None), "id", None)
        artist_name = getattr(getattr(t, "artist", None), "name", "Artista desconocido")
        cover_url = ""
        try:
            if hasattr(t, "album") and t.album:
                cover_url = t.album.image(640)
        except Exception:
            pass

        return {
            "id": t.id,
            "type": "track",
            "name": t.name,
            "artist": artist_name,
            "album": album_name,
            "album_id": album_id,
            "duration": t.duration,
            "duration_str": format_duration(t.duration),
            "cover_url": cover_url,
            "quality": str(getattr(t, "audio_quality", "LOSSLESS")),
            "explicit": bool(getattr(t, "explicit", False)),
            "raw_obj": t,
        }
    except Exception as e:
        log.error("Error obteniendo detalles del track %s: %s", track_id, e)
        return None


def get_album_tracks(album_id: int) -> List[Dict[str, Any]]:
    client = get_client()
    try:
        alb = client.session.album(album_id)
        tracks = client.get_album_tracks(alb)
        results = []
        cover_url = alb.image(640) if hasattr(alb, "image") else ""
        for t in tracks:
            results.append({
                "id": t.id,
                "type": "track",
                "track_num": getattr(t, "track_num", 1),
                "name": t.name,
                "artist": getattr(getattr(t, "artist", None), "name", getattr(alb.artist, "name", "")),
                "album": alb.name,
                "album_id": alb.id,
                "duration": t.duration,
                "duration_str": format_duration(t.duration),
                "cover_url": cover_url,
                "quality": str(getattr(t, "audio_quality", "LOSSLESS")).replace("AudioQuality.", ""),
                "explicit": bool(getattr(t, "explicit", False)),
                "raw_obj": t,
            })
        return results
    except Exception as e:
        log.error("Error obteniendo pistas del álbum %s: %s", album_id, e)
        return []


def get_track_stream_url(track_or_id: Any) -> Optional[str]:
    client = get_client()
    try:
        if isinstance(track_or_id, (int, str)):
            track = client.get_track(int(track_or_id))
        else:
            track = track_or_id
        if not track:
            return None
        return client.get_track_url(track)
    except Exception as e:
        log.error("Error obteniendo stream URL: %s", e)
        return None


def fetch_lrclib_lyrics(title: str, artist: str, album: str = "", duration: float = 0.0) -> Tuple[str, List[Dict[str, Any]]]:
    """Fallback lyrics provider using the free open LRCLIB database."""
    if not title:
        return "", []

    headers = {"User-Agent": "TidalPlayer/1.0 (Serpantinum Hi-Fi; https://github.com)"}

    # Limpiar sufijos típicos de títulos que suelen arruinar búsquedas exactas (remasters, live, etc.)
    clean_title = re.sub(r"\s*[\(\[](?:remaster(?:ed)?|live|radio edit|deluxe|version|feat\.?).*?[\)\]]", "", title, flags=re.IGNORECASE).strip() or title
    clean_artist = re.sub(r"\s*[\(\[].*?[\)\]]", "", artist).strip() or artist

    data = None
    # 1. Intentar obtención directa exacta en LRCLIB
    params = {"artist_name": clean_artist, "track_name": clean_title}
    if album:
        clean_album = re.sub(r"\s*[\(\[].*?[\)\]]", "", album).strip() or album
        params["album_name"] = clean_album
    if duration > 0:
        params["duration"] = int(duration)

    try:
        url = "https://lrclib.net/api/get?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        data = None

    # 2. Si falló la consulta exacta, buscar en el catálogo general de LRCLIB
    if not data or (not data.get("syncedLyrics") and not data.get("plainLyrics")):
        try:
            q = f"{clean_artist} {clean_title}".strip()
            s_url = "https://lrclib.net/api/search?" + urllib.parse.urlencode({"q": q})
            s_req = urllib.request.Request(s_url, headers=headers)
            with urllib.request.urlopen(s_req, timeout=3.5) as resp:
                results = json.loads(resp.read().decode("utf-8"))
                if results and isinstance(results, list):
                    # Priorizar aquel que tenga letras sincronizadas
                    data = next((r for r in results if r.get("syncedLyrics")), results[0])
        except Exception as e:
            log.debug("LRCLIB search error para '%s - %s': %s", artist, title, e)

    if not data:
        return "", []

    synced_raw = data.get("syncedLyrics") or ""
    plain = data.get("plainLyrics") or ""

    parsed = []
    if synced_raw:
        lines = parse_lrc(synced_raw)
        for line in lines:
            parsed.append({"timestamp": line.timestamp, "text": line.text})

    return plain, parsed


def get_track_lyrics(track_or_id: Any, title: str = "", artist: str = "", album: str = "", duration: float = 0.0) -> Tuple[str, List[Dict[str, Any]]]:
    """Returns (plain_text, list_of_{timestamp, text}).
    Queries Tidal first. If Tidal has no lyrics, falls back to LRCLIB.
    """
    client = get_client()
    plain, parsed = "", []
    t_title = title
    t_artist = artist
    t_album = album
    t_dur = duration

    # 1. Intentar obtener desde Tidal
    try:
        track = None
        if isinstance(track_or_id, (int, str)) and str(track_or_id).isdigit():
            track = client.get_track(int(track_or_id))
        elif hasattr(track_or_id, "id"):
            track = track_or_id

        if track:
            if not t_title and hasattr(track, "name"):
                t_title = track.name
            if not t_artist and hasattr(track, "artist"):
                t_artist = getattr(track.artist, "name", "")
            if not t_album and hasattr(track, "album"):
                t_album = getattr(track.album, "name", "")
            if not t_dur and hasattr(track, "duration"):
                t_dur = track.duration

            p, lrc = client.get_lyrics(track)
            if p or lrc:
                plain = p or ""
                if lrc:
                    lines = parse_lrc(lrc)
                    for line in lines:
                        parsed.append({"timestamp": line.timestamp, "text": line.text})
    except Exception as e:
        log.warning("Tidal no devolvió letras para track: %s", e)

    # 2. Si Tidal no tiene letras sincronizadas ni planas, recurrir a LRCLIB
    if not plain and not parsed:
        if t_title:
            log.info("Consultando letras en repositorio alternativo (LRCLIB) para: %s - %s", t_artist, t_title)
            plain, parsed = fetch_lrclib_lyrics(t_title, t_artist, t_album, t_dur)

    return plain, parsed


def get_user_playlists() -> List[Dict[str, Any]]:
    """Obtiene las playlists creadas y favoritas del usuario actual."""
    client = get_client()
    seen = set()
    results = []
    try:
        pls = client.session.user.playlists() or []
    except Exception as e:
        log.warning("No se pudieron obtener playlists del usuario: %s", e)
        pls = []
    try:
        favs = client.session.user.favorites.playlists() or []
    except Exception as e:
        log.warning("No se pudieron obtener playlists favoritas: %s", e)
        favs = []

    for p in list(pls) + list(favs):
        p_id = str(p.id)
        if p_id in seen:
            continue
        seen.add(p_id)
        cover_url = ""
        try:
            if hasattr(p, "image"):
                cover_url = p.image(640)
        except Exception:
            pass
        results.append({
            "id": p_id,
            "type": "playlist",
            "name": p.name,
            "creator": getattr(getattr(p, "creator", None), "name", "Tú"),
            "num_tracks": getattr(p, "num_tracks", 0),
            "cover_url": cover_url,
            "is_user": True,
        })
    return results


def search_playlists(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Busca playlists en el catálogo general de Tidal."""
    client = get_client()
    try:
        raw = client.search(query, limit=limit)
        pls = raw.get("playlists", [])
    except Exception as e:
        log.error("Error buscando playlists: %s", e)
        return []

    results = []
    for p in pls:
        cover_url = ""
        try:
            if hasattr(p, "image"):
                cover_url = p.image(640)
        except Exception:
            pass
        results.append({
            "id": str(p.id),
            "type": "playlist",
            "name": p.name,
            "creator": getattr(getattr(p, "creator", None), "name", "Tidal"),
            "num_tracks": getattr(p, "num_tracks", 0),
            "cover_url": cover_url,
            "is_user": False,
        })
    return results


def get_playlist_tracks(playlist_id: str) -> List[Dict[str, Any]]:
    """Obtiene todas las pistas contenidas en una playlist."""
    client = get_client()
    try:
        pl = client.session.playlist(str(playlist_id))
        tracks = pl.tracks()
        results = []
        cover_url = pl.image(640) if hasattr(pl, "image") else ""
        for idx, t in enumerate(tracks):
            album_name = getattr(getattr(t, "album", None), "name", "")
            album_id = getattr(getattr(t, "album", None), "id", None)
            t_cover = ""
            try:
                if hasattr(t, "album") and t.album:
                    t_cover = t.album.image(640)
            except Exception:
                t_cover = cover_url
            results.append({
                "id": t.id,
                "type": "track",
                "track_num": idx + 1,
                "name": t.name,
                "artist": getattr(getattr(t, "artist", None), "name", "Artista desconocido"),
                "album": album_name,
                "album_id": album_id,
                "duration": t.duration,
                "duration_str": format_duration(t.duration),
                "cover_url": t_cover or cover_url,
                "quality": str(getattr(t, "audio_quality", "LOSSLESS")).replace("AudioQuality.", ""),
                "explicit": bool(getattr(t, "explicit", False)),
                "raw_obj": t,
            })
        return results
    except Exception as e:
        log.error("Error obteniendo pistas de playlist %s: %s", playlist_id, e)
        return []


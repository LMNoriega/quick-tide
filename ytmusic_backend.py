#!/usr/bin/env python3
"""
Quick-Tide YouTube Music Backend
Zero-login audio streaming and search powered by yt-dlp and LRCLIB.
Delivers high-bitrate Opus audio streams natively to MPV without an account.
"""

from __future__ import annotations

import os
import re
import time
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import yt_dlp

log = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".cache" / "tidal-gui" / "covers"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

COOKIES_FILE = os.path.expanduser("~/.config/quick-tide/youtube_cookies.txt")

_stream_url_cache: Dict[str, Tuple[str, float]] = {}


def get_ydl_opts(extra_opts: Optional[dict] = None) -> dict:
    opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    if os.path.isfile(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 50:
        opts["cookiefile"] = COOKIES_FILE
    if extra_opts:
        opts.update(extra_opts)
    return opts


def is_logged_in() -> bool:
    """Returns True if cookies file exists and has content."""
    return os.path.isfile(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 50


def sync_browser_cookies() -> Tuple[bool, str]:
    """
    Attempts to extract YouTube cookies from installed browsers (Zen Browser, Chromium, Firefox)
    and saves them to ~/.config/quick-tide/youtube_cookies.txt.
    """
    import glob
    candidates = []

    # 1. Zen Browser profile
    zen_profiles = glob.glob(os.path.expanduser("~/.config/zen/*Default*"))
    for zp in zen_profiles:
        if os.path.isfile(os.path.join(zp, "cookies.sqlite")):
            candidates.append(("firefox", zp, "Zen Browser"))

    # 2. Chromium
    candidates.append(("chromium", None, "Chromium"))

    # 3. Firefox standard
    ff_profiles = glob.glob(os.path.expanduser("~/.mozilla/firefox/*.default*"))
    for fp in ff_profiles:
        if os.path.isfile(os.path.join(fp, "cookies.sqlite")):
            candidates.append(("firefox", fp, "Firefox"))

    os.makedirs(os.path.dirname(COOKIES_FILE), exist_ok=True)

    for browser_type, profile_path, display_name in candidates:
        try:
            ydl_opts = {
                "cookiesfrombrowser": (browser_type, profile_path, None, None),
                "cookiefile": COOKIES_FILE,
                "quiet": True,
                "skip_download": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                cj = ydl.cookiejar
                yt_c = [c for c in cj if "youtube.com" in getattr(c, "domain", "")]
                if yt_c:
                    cj.save(COOKIES_FILE, ignore_discard=True, ignore_expires=True)
                    log.info("Extracted %d YouTube cookies from %s", len(yt_c), display_name)
                    return True, f"Sincronizado con éxito desde {display_name} ({len(yt_c)} cookies)"
        except Exception as e:
            log.debug("Cookie extraction from %s failed: %s", display_name, e)

    return False, "No se encontraron cookies activas de YouTube en los navegadores del sistema."


def get_user_playlists() -> List[Dict[str, Any]]:
    """Fetches the authenticated user's YouTube playlists if logged in."""
    if not is_logged_in():
        return []

    ydl_opts = get_ydl_opts({
        "extract_flat": True,
    })
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info("https://www.youtube.com/feed/playlists", download=False)
            entries = res.get("entries", [])
            for e in entries:
                if not e:
                    continue
                v_id = e.get("id")
                title = e.get("title", "Playlist")
                uploader = e.get("uploader", "Tú")
                thumbnails = e.get("thumbnails") or []
                cover_url = thumbnails[-1].get("url") if thumbnails else e.get("thumbnail", "")

                results.append({
                    "id": v_id,
                    "type": "playlist",
                    "provider": "youtube",
                    "name": title,
                    "creator": uploader or "Tú",
                    "num_tracks": e.get("playlist_count") or 0,
                    "cover_url": cover_url,
                    "is_user": True,
                })
    except Exception as e:
        log.warning("No se pudieron cargar las playlists de usuario de YouTube: %s", e)

    return results


def format_duration(seconds: int | float | None) -> str:
    if not seconds:
        return "0:00"
    s = int(seconds)
    mins = s // 60
    secs = s % 60
    return f"{mins}:{secs:02d}"


def clean_youtube_title(raw_title: str, uploader: str = "") -> Tuple[str, str]:
    """
    Cleans up typical YouTube video titles into (clean_title, artist).
    Handles 'Artist - Title (Official Video)' -> ('Title', 'Artist').
    """
    cleaned = re.sub(
        r"\s*[\(\[](?:official\s*(?:video|audio|music\s*video|lyric\s*video|visualizer)?|lyrics?|hd|4k|remaster(?:ed)?|audio|clip\s*officiel|video\s*oficial).*?[\)\]]",
        "",
        raw_title,
        flags=re.IGNORECASE,
    ).strip() or raw_title

    cleaned = re.sub(r"\s*\b(?:ft\.?|feat\.?|featuring)\b.*", "", cleaned, flags=re.IGNORECASE).strip()

    if " - " in cleaned:
        parts = cleaned.split(" - ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    elif " – " in cleaned:
        parts = cleaned.split(" – ", 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    elif ":" in cleaned:
        parts = cleaned.split(":", 1)
        artist = parts[0].strip()
        title = parts[1].strip()
    else:
        title = cleaned
        artist = uploader.replace(" - Topic", "").replace("VEVO", "").strip() or "YouTube Music"

    return title, artist


def fetch_highres_cover_url(artist: str, title: str) -> str:
    """Queries iTunes Search API (1400x1400) and Deezer API (1000x1000) for pristine square album covers."""
    if not (artist and title) or artist == "YouTube Music":
        return ""
    clean_t = re.sub(r"\s*[\(\[].*?[\)\]]", "", title).strip() or title
    clean_a = re.sub(r"\s*[\(\[].*?[\)\]]", "", artist).strip() or artist

    # 1. iTunes 1400x1400 square cover
    try:
        query = f"{clean_a} {clean_t}"
        url = "https://itunes.apple.com/search?" + urllib.parse.urlencode({"term": query, "entity": "song", "limit": 1})
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            import json
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            if results:
                raw_art = results[0].get("artworkUrl100", "")
                if raw_art:
                    return raw_art.replace("100x100bb", "1400x1400bb")
    except Exception:
        pass

    # 2. Deezer 1000x1000 square cover
    try:
        query = f"{clean_a} {clean_t}"
        url = "https://api.deezer.com/search?" + urllib.parse.urlencode({"q": query, "limit": 1})
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            import json
            data = json.loads(resp.read().decode())
            data_list = data.get("data", [])
            if data_list:
                album = data_list[0].get("album", {})
                cover = album.get("cover_xl") or album.get("cover_big")
                if cover:
                    return cover
    except Exception:
        pass

    return ""


def download_cover(url: str | None, key: str | int, track: Optional[Dict[str, Any]] = None) -> str:
    """Download cover image to cache and return local file path.
    For YouTube Music, attempts to fetch pristine square album art from iTunes/Deezer first."""
    local_path = CACHE_DIR / f"yt_{key}.jpg"
    if local_path.is_file() and local_path.stat().st_size > 0:
        return str(local_path)

    artist = ""
    title = ""
    if track and isinstance(track, dict):
        artist = str(track.get("artist") or "")
        title = str(track.get("name") or "")

    # Try high-res square cover from iTunes/Deezer
    highres_url = ""
    if artist and title:
        highres_url = fetch_highres_cover_url(artist, title)

    download_target = highres_url or url
    if not download_target:
        return ""

    try:
        req = urllib.request.Request(
            download_target,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            img_data = resp.read()

        # If it was a YouTube thumbnail fallback (likely 16:9), center-crop to 1:1 square
        if not highres_url and (download_target == url):
            try:
                import io
                from PIL import Image
                im = Image.open(io.BytesIO(img_data))
                w, h = im.size
                if w != h and w > 0 and h > 0:
                    min_dim = min(w, h)
                    left = (w - min_dim) // 2
                    top = (h - min_dim) // 2
                    im_cropped = im.crop((left, top, left + min_dim, top + min_dim))
                    im_cropped.convert("RGB").save(local_path, "JPEG", quality=92)
                    return str(local_path)
            except Exception:
                pass

        with open(local_path, "wb") as f:
            f.write(img_data)
        return str(local_path)
    except Exception as e:
        log.warning("Error descargando carátula YouTube %s: %s", download_target, e)
        return ""


def search_tracks(query: str, limit: int = 35) -> List[Dict[str, Any]]:
    """Search YouTube Music / YouTube for tracks with Opus stream quality."""
    ydl_opts = get_ydl_opts({
        "format": "bestaudio/best",
        "extract_flat": "in_playlist",
    })
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch{limit}:{query} audio", download=False)
            entries = res.get("entries", [])
            for e in entries:
                if not e:
                    continue
                v_id = e.get("id")
                raw_title = e.get("title", "")
                uploader = e.get("uploader", "")
                title, artist = clean_youtube_title(raw_title, uploader)
                duration = e.get("duration") or 0

                # Thumbnail resolution
                thumbnails = e.get("thumbnails") or []
                cover_url = thumbnails[-1].get("url") if thumbnails else e.get("thumbnail", "")

                results.append({
                    "id": v_id,
                    "type": "track",
                    "provider": "youtube",
                    "name": title,
                    "artist": artist,
                    "album": "YouTube Music",
                    "duration": duration,
                    "duration_str": format_duration(duration),
                    "cover_url": cover_url,
                    "quality": "OPUS",
                    "explicit": False,
                    "raw_url": f"https://www.youtube.com/watch?v={v_id}",
                })
    except Exception as e:
        log.error("Error buscando en YouTube Music: %s", e)

    return results


def search_albums(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Search for full albums or music compilations on YouTube."""
    ydl_opts = get_ydl_opts({
        "format": "bestaudio/best",
        "extract_flat": "in_playlist",
    })
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch{limit}:{query} full album", download=False)
            entries = res.get("entries", [])
            for e in entries:
                if not e:
                    continue
                v_id = e.get("id")
                raw_title = e.get("title", "")
                uploader = e.get("uploader", "")
                title, artist = clean_youtube_title(raw_title, uploader)
                thumbnails = e.get("thumbnails") or []
                cover_url = thumbnails[-1].get("url") if thumbnails else e.get("thumbnail", "")

                results.append({
                    "id": v_id,
                    "type": "album",
                    "provider": "youtube",
                    "name": title,
                    "artist": artist,
                    "num_tracks": 1,
                    "year": "",
                    "cover_url": cover_url,
                })
    except Exception as e:
        log.error("Error buscando álbumes en YouTube: %s", e)

    return results


def search_playlists(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """Search for music playlists on YouTube."""
    ydl_opts = get_ydl_opts({
        "extract_flat": True,
    })
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(f"ytsearch{limit}:{query} playlist", download=False)
            entries = res.get("entries", [])
            for e in entries:
                if not e:
                    continue
                v_id = e.get("id")
                title = e.get("title", "Playlist")
                uploader = e.get("uploader", "YouTube")
                thumbnails = e.get("thumbnails") or []
                cover_url = thumbnails[-1].get("url") if thumbnails else e.get("thumbnail", "")

                results.append({
                    "id": v_id,
                    "type": "playlist",
                    "provider": "youtube",
                    "name": title,
                    "creator": uploader,
                    "num_tracks": e.get("playlist_count") or 0,
                    "cover_url": cover_url,
                    "is_user": False,
                })
    except Exception as e:
        log.error("Error buscando playlists en YouTube: %s", e)

    return results


def get_track_details(track_id: str) -> Optional[Dict[str, Any]]:
    """Extract full metadata for a single YouTube track."""
    url = f"https://www.youtube.com/watch?v={track_id}" if not track_id.startswith("http") else track_id
    ydl_opts = get_ydl_opts({
        "format": "bestaudio/best",
    })
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            e = ydl.extract_info(url, download=False)
            if not e:
                return None
            v_id = e.get("id", track_id)
            raw_title = e.get("title", "")
            uploader = e.get("uploader", "")
            title, artist = clean_youtube_title(raw_title, uploader)
            duration = e.get("duration") or 0
            thumbnails = e.get("thumbnails") or []
            cover_url = thumbnails[-1].get("url") if thumbnails else e.get("thumbnail", "")

            return {
                "id": v_id,
                "type": "track",
                "provider": "youtube",
                "name": title,
                "artist": artist,
                "album": "YouTube Music",
                "duration": duration,
                "duration_str": format_duration(duration),
                "cover_url": cover_url,
                "quality": "OPUS",
                "explicit": False,
                "raw_url": f"https://www.youtube.com/watch?v={v_id}",
            }
    except Exception as e:
        log.error("Error obteniendo detalles del track de YouTube %s: %s", track_id, e)
        return None


def get_album_tracks(album_id: str) -> List[Dict[str, Any]]:
    """Get tracks for a YouTube album/video."""
    t = get_track_details(album_id)
    return [t] if t else []


def get_playlist_tracks(playlist_id: str) -> List[Dict[str, Any]]:
    """Get tracks contained in a YouTube playlist."""
    url = f"https://www.youtube.com/playlist?list={playlist_id}" if not playlist_id.startswith("http") else playlist_id
    ydl_opts = get_ydl_opts({
        "extract_flat": True,
    })
    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(url, download=False)
            entries = res.get("entries", [])
            for idx, e in enumerate(entries):
                if not e:
                    continue
                v_id = e.get("id")
                raw_title = e.get("title", "")
                uploader = e.get("uploader", "")
                title, artist = clean_youtube_title(raw_title, uploader)
                duration = e.get("duration") or 0
                thumbnails = e.get("thumbnails") or []
                cover_url = thumbnails[-1].get("url") if thumbnails else e.get("thumbnail", "")

                results.append({
                    "id": v_id,
                    "type": "track",
                    "provider": "youtube",
                    "track_num": idx + 1,
                    "name": title,
                    "artist": artist,
                    "album": res.get("title", "YouTube Playlist"),
                    "duration": duration,
                    "duration_str": format_duration(duration),
                    "cover_url": cover_url,
                    "quality": "OPUS",
                    "explicit": False,
                    "raw_url": f"https://www.youtube.com/watch?v={v_id}",
                })
    except Exception as e:
        log.error("Error obteniendo pistas de playlist de YouTube %s: %s", playlist_id, e)

    return results


def get_track_stream_url(track_or_id: Any) -> Optional[str]:
    """
    Resolves the direct audio stream URL or returns the YouTube URL for MPV.
    MPV handles yt-dlp URLs directly with:
    loadfile https://www.youtube.com/watch?v=...
    """
    v_id = None
    if isinstance(track_or_id, dict):
        v_id = track_or_id.get("id")
    else:
        v_id = str(track_or_id)

    if not v_id:
        return None

    # Check cache (valid for 20 minutes)
    cached = _stream_url_cache.get(v_id)
    if cached and (time.time() - cached[1] < 1200):
        return cached[0]

    # In modern MPV, passing the YouTube watch URL works directly via ytdl hook
    watch_url = f"https://www.youtube.com/watch?v={v_id}"
    _stream_url_cache[v_id] = (watch_url, time.time())
    return watch_url

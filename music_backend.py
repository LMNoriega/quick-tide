#!/usr/bin/env python3
"""
Quick-Tide Music Backend Dispatcher
Routes search, playback streams, covers and lyrics to the selected service:
- 'tidal': Tidal Hi-Res / Lossless streaming (OAuth session)
- 'youtube': YouTube Music Opus streaming (zero login required)
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional, Tuple

import config
import tidal_backend
import ytmusic_backend

log = logging.getLogger(__name__)


def get_active_service() -> str:
    """Returns 'tidal' or 'youtube'."""
    return config.get_active_service()


def set_active_service(service: str) -> None:
    """Sets active service in config.toml."""
    config.set_active_service(service)


def is_service_ready(service: str) -> bool:
    """Checks if the service is ready to stream."""
    if service == "youtube":
        return True
    if service == "tidal":
        return tidal_backend.is_logged_in()
    return False


def get_current_provider(item: Optional[Dict[str, Any]] = None):
    """Returns the backend module for the given item or active service."""
    if item and isinstance(item, dict) and item.get("provider") == "youtube":
        return ytmusic_backend
    svc = get_active_service()
    if svc == "youtube":
        return ytmusic_backend
    return tidal_backend


def search_tracks(query: str, limit: int = 35) -> List[Dict[str, Any]]:
    provider = get_current_provider()
    tracks = provider.search_tracks(query, limit=limit)
    svc = "youtube" if provider == ytmusic_backend else "tidal"
    for t in tracks:
        t["provider"] = svc
    return tracks


def search_albums(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    provider = get_current_provider()
    albums = provider.search_albums(query, limit=limit)
    svc = "youtube" if provider == ytmusic_backend else "tidal"
    for a in albums:
        a["provider"] = svc
    return albums


def search_playlists(query: str, limit: int = 30) -> List[Dict[str, Any]]:
    provider = get_current_provider()
    playlists = provider.search_playlists(query, limit=limit)
    svc = "youtube" if provider == ytmusic_backend else "tidal"
    for p in playlists:
        p["provider"] = svc
    return playlists


def get_album_tracks(album_id: Any, provider_name: Optional[str] = None) -> List[Dict[str, Any]]:
    if provider_name == "youtube" or str(album_id).startswith("yt_") or (isinstance(album_id, str) and not album_id.isdigit()):
        tracks = ytmusic_backend.get_album_tracks(str(album_id).replace("yt_", ""))
        for t in tracks:
            t["provider"] = "youtube"
        return tracks
    try:
        tracks = tidal_backend.get_album_tracks(int(album_id))
        for t in tracks:
            t["provider"] = "tidal"
        return tracks
    except Exception:
        tracks = ytmusic_backend.get_album_tracks(str(album_id))
        for t in tracks:
            t["provider"] = "youtube"
        return tracks


def get_playlist_tracks(playlist_id: str, provider_name: Optional[str] = None) -> List[Dict[str, Any]]:
    if provider_name == "youtube" or playlist_id.startswith("yt_") or playlist_id.startswith("PL"):
        tracks = ytmusic_backend.get_playlist_tracks(playlist_id.replace("yt_", ""))
        for t in tracks:
            t["provider"] = "youtube"
        return tracks
    try:
        tracks = tidal_backend.get_playlist_tracks(playlist_id)
        for t in tracks:
            t["provider"] = "tidal"
        return tracks
    except Exception:
        tracks = ytmusic_backend.get_playlist_tracks(playlist_id)
        for t in tracks:
            t["provider"] = "youtube"
        return tracks


def get_track_details(track_id: Any, provider_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    if provider_name == "youtube" or (isinstance(track_id, str) and not track_id.isdigit()):
        t = ytmusic_backend.get_track_details(str(track_id))
        if t:
            t["provider"] = "youtube"
        return t
    try:
        t = tidal_backend.get_track_details(int(track_id))
        if t:
            t["provider"] = "tidal"
        return t
    except Exception:
        t = ytmusic_backend.get_track_details(str(track_id))
        if t:
            t["provider"] = "youtube"
        return t


def get_track_stream_url(track_or_id: Any) -> Optional[str]:
    """Resolves audio stream URL using either Tidal or YouTube Music."""
    if isinstance(track_or_id, dict):
        prov = track_or_id.get("provider")
        t_id = track_or_id.get("id")
        if prov == "youtube" or (isinstance(t_id, str) and not t_id.isdigit()):
            return ytmusic_backend.get_track_stream_url(track_or_id)
        if prov == "tidal" or (isinstance(t_id, int) or (isinstance(t_id, str) and t_id.isdigit())):
            return tidal_backend.get_track_stream_url(track_or_id)
    elif isinstance(track_or_id, str) and not track_or_id.isdigit():
        return ytmusic_backend.get_track_stream_url(track_or_id)

    # Default fallback
    try:
        url = tidal_backend.get_track_stream_url(track_or_id)
        if url:
            return url
    except Exception:
        pass
    return ytmusic_backend.get_track_stream_url(track_or_id)


def download_cover(url: str | None, key: str | int) -> str:
    if not url:
        return ""
    if "youtube.com" in url or "ytimg.com" in url or (isinstance(key, str) and not str(key).isdigit()):
        return ytmusic_backend.download_cover(url, key)
    return tidal_backend.download_cover(url, key)


def get_track_lyrics(track_or_id: Any, title: str = "", artist: str = "", album: str = "", duration: float = 0.0) -> Tuple[str, List[Dict[str, Any]]]:
    """Provides synchronized lyrics via Tidal or LRCLIB."""
    prov = "tidal"
    if isinstance(track_or_id, dict):
        prov = track_or_id.get("provider", "tidal")
    elif isinstance(track_or_id, str) and not track_or_id.isdigit():
        prov = "youtube"

    if prov == "tidal":
        return tidal_backend.get_track_lyrics(track_or_id, title, artist, album, duration)
    return tidal_backend.fetch_lrclib_lyrics(title, artist, album, duration)


def get_user_playlists() -> List[Dict[str, Any]]:
    svc = get_active_service()
    if svc == "tidal" and tidal_backend.is_logged_in():
        pls = tidal_backend.get_user_playlists()
        for p in pls:
            p["provider"] = "tidal"
        return pls
    elif svc == "youtube" and ytmusic_backend.is_logged_in():
        pls = ytmusic_backend.get_user_playlists()
        for p in pls:
            p["provider"] = "youtube"
        return pls
    return []

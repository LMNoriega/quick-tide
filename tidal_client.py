from __future__ import annotations

import datetime
import json
import logging
import os
import tempfile
import threading
import time
from typing import Optional, Tuple, Callable

_tidalapi = None
_QUALITY_MAP = None
_QUALITY_ORDER = None


def _get_tidalapi():
    global _tidalapi, _QUALITY_MAP, _QUALITY_ORDER
    if _tidalapi is None:
        import tidalapi
        from tidalapi.media import Quality
        _tidalapi = tidalapi
        _QUALITY_MAP = {
            "low": Quality.low_96k,
            "high": Quality.low_320k,
            "lossless": Quality.high_lossless,
            "hi_res": Quality.hi_res_lossless,
            "max": Quality.hi_res_lossless,
        }
        _QUALITY_ORDER = [
            Quality.hi_res_lossless,
            Quality.high_lossless,
            Quality.low_320k,
            Quality.low_96k,
        ]
    return _tidalapi


class TidalClient:
    def __init__(self):
        self._api_lock = threading.Lock()
        self._quality_lock = threading.Lock()
        self._last_call_time = 0.0
        tapi = _get_tidalapi()
        quality = _QUALITY_MAP.get("lossless")
        self.session = tapi.Session(tapi.Config(quality=quality))
        self._quality_floor = 0
        self._manifest_dir = os.path.join(tempfile.gettempdir(), "quick-tide-manifests")
        self._clear_manifests()
        os.makedirs(self._manifest_dir, exist_ok=True)
        self._try_load_tokens()

    def _clear_manifests(self) -> None:
        import shutil
        shutil.rmtree(self._manifest_dir, ignore_errors=True)

    def _throttle(self) -> None:
        with self._api_lock:
            now = time.monotonic()
            wait = _MIN_CALL_INTERVAL - (now - self._last_call_time)
            if wait > 0:
                time.sleep(wait)
            self._last_call_time = time.monotonic()

    def _api_call(self, fn, *args, **kwargs):
        from tidalapi.exceptions import TooManyRequests
        for attempt in range(_MAX_RETRIES):
            self._throttle()
            try:
                return fn(*args, **kwargs)
            except TooManyRequests as e:
                wait = max(1, getattr(e, "retry_after", None) or 5)
                log.warning(
                    "TIDAL rate limit; retrying in %ss (attempt %d/%d)",
                    wait, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(wait)
        self._throttle()
        return fn(*args, **kwargs)

    def _try_load_tokens(self) -> bool:
        session_paths = [QUICKTIDE_SESSION, LOWTIDE_SESSION]
        for p in session_paths:
            if os.path.isfile(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    expiry = None
                    if data.get("expiry_time"):
                        expiry = datetime.datetime.fromisoformat(data["expiry_time"])
                    self.session.load_oauth_session(
                        token_type=data.get("token_type", "Bearer"),
                        access_token=data["access_token"],
                        refresh_token=data.get("refresh_token"),
                        expiry_time=expiry,
                    )
                    if self.session.check_login():
                        log.info("TIDAL session loaded successfully from %s", p)
                        return True
                except Exception as e:
                    log.warning("Could not load TIDAL session from %s: %s", p, e)
        return False

    def save_tokens(self) -> None:
        os.makedirs(QUICKTIDE_DIR, exist_ok=True)
        expiry = getattr(self.session, "expiry_time", None)
        data = {
            "access_token": self.session.access_token,
            "refresh_token": self.session.refresh_token,
            "token_type": getattr(self.session, "token_type", "Bearer"),
            "expiry_time": expiry.isoformat() if expiry else None,
        }
        with open(QUICKTIDE_SESSION, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        log.info("TIDAL session tokens saved to %s", QUICKTIDE_SESSION)

    def is_logged_in(self) -> bool:
        try:
            return bool(self.session.check_login())
        except Exception:
            return False

    def start_oauth_login(self, on_success: Optional[Callable[[str], None]] = None, on_error: Optional[Callable[[str], None]] = None) -> Tuple[str, str]:
        """
        Inicia el flujo de autenticación OAuth de TIDAL con dispositivo.
        Devuelve (auth_url, user_code) y arranca un hilo en background que espera la confirmación en el navegador.
        """
        login_info, future = self.session.login_oauth()
        auth_url = getattr(login_info, "verification_uri_complete", "") or f"https://link.tidal.com/{getattr(login_info, 'user_code', '')}"
        user_code = getattr(login_info, "user_code", "")

        def _wait_login():
            try:
                future.result(timeout=getattr(login_info, "expires_in", 300))
                self.save_tokens()
                user_name = getattr(getattr(self.session, "user", None), "name", None) or "Usuario"
                log.info("TIDAL OAuth login successful for %s", user_name)
                if on_success:
                    on_success(user_name)
            except Exception as e:
                log.warning("TIDAL OAuth login failed: %s", e)
                if on_error:
                    on_error(str(e))

        threading.Thread(target=_wait_login, daemon=True).start()
        return auth_url, user_code

    def me(self):
        return self.session.user

    def search(self, query: str, limit: int = 50) -> dict:
        return self._api_call(self.session.search, query, limit=limit)

    def get_user_playlists(self) -> list:
        return self._api_call(self.session.user.playlists)

    def get_album_tracks(self, album) -> list:
        return self._api_call(album.tracks)

    def get_playlist_tracks(self, playlist) -> list:
        fn = playlist.tracks if hasattr(playlist, "tracks") else playlist.items
        return self._api_call(fn)

    def get_track(self, track_id: int):
        return self._api_call(self.session.track, track_id)

    def get_track_url(self, track) -> Optional[str]:
        name = getattr(track, "name", "?")
        for idx in range(self._quality_floor, len(_QUALITY_ORDER)):
            quality = _QUALITY_ORDER[idx]
            try:
                return self._resolve_stream(track, quality)
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status in (401, 403):
                    self._quality_floor = idx + 1
        return None

    def _resolve_stream(self, track, quality) -> Optional[str]:
        with self._quality_lock:
            prev = self.session.config.quality
            self.session.config.quality = quality
            try:
                stream = self._api_call(track.get_stream)
            finally:
                self.session.config.quality = prev

        manifest = stream.get_stream_manifest()
        if getattr(manifest, "manifest_mime_type", "") == "application/dash+xml":
            return self._write_manifest(stream.manifest)
        urls = manifest.get_urls()
        return urls[0] if urls else None

    def _write_manifest(self, b64_manifest: str) -> str:
        import base64
        os.makedirs(self._manifest_dir, exist_ok=True)
        fd, path = tempfile.mkstemp(suffix=".mpd", dir=self._manifest_dir)
        with os.fdopen(fd, "wb") as f:
            f.write(base64.b64decode(b64_manifest))
        return path

    def get_lyrics(self, track) -> tuple[str, str]:
        try:
            lyr = self._api_call(track.lyrics)
            return lyr.text or "", lyr.subtitles or ""
        except Exception:
            return "", ""

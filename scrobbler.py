#!/usr/bin/env python3
"""
Quick-Tide Last.fm Scrobbler Module
Native integration with Last.fm API 2.0 (Now Playing + Scrobbles) using pylast.
Completely non-blocking, background-threaded, and resilient.
"""

from __future__ import annotations

import os
import sys
import time
import logging
import hashlib
import threading
from typing import Optional, Dict, Any, Tuple, List

log = logging.getLogger(__name__)

# Ensure local share and lowtide venv are in sys.path
SHARE_DIR = os.path.dirname(os.path.abspath(__file__))
if SHARE_DIR not in sys.path:
    sys.path.insert(0, SHARE_DIR)

import config


class QuickTideScrobbler:
    """Manages Last.fm authentication, Now Playing notifications, and scrobbling."""

    def __init__(self, cfg: Optional[Dict[str, Any]] = None):
        if cfg is None:
            cfg = config.get_lastfm_config()

        self.cfg = dict(cfg)
        self.enabled: bool = bool(self.cfg.get("enabled", False))
        self.username: str = str(self.cfg.get("username", "")).strip()
        self.api_key: str = str(self.cfg.get("api_key", "")).strip()
        self.api_secret: str = str(self.cfg.get("api_secret", "")).strip()
        self.session_key: str = str(self.cfg.get("session_key", "")).strip()
        self.password_hash: str = str(self.cfg.get("password_hash", "")).strip()
        password = str(self.cfg.get("password", "")).strip()

        if password and not self.password_hash:
            self.password_hash = hashlib.md5(password.encode("utf-8")).hexdigest()

        self._network = None
        self._connected: bool = False
        self._status: str = "off" if not self.enabled else "connecting"
        self._last_error: str = ""
        self._lock = threading.RLock()

        # Track tracking
        self._current_track: Optional[Dict[str, Any]] = None
        self._track_start_time: int = 0
        self._scrobbled: bool = False
        self._last_scrobble_ts: float = 0.0
        self._last_scrobbled_title: str = ""
        self._pending_scrobbles: List[Dict[str, Any]] = []

        # Background worker thread for initialization
        if self.enabled:
            threading.Thread(target=self._init_network, daemon=True).start()

    def _init_network(self) -> None:
        """Authenticate with Last.fm in the background without blocking the UI."""
        if not self.enabled:
            self._status = "off"
            return

        has_creds = bool(self.api_key and self.api_secret and (self.session_key or (self.username and self.password_hash)))
        if not has_creds:
            with self._lock:
                self._connected = False
                self._status = "unconfigured"
                self._last_error = "Credenciales incompletas en ~/.config/quick-tide/config.toml"
            log.info("Last.fm habilitado pero faltan credenciales (api_key, api_secret o usuario)")
            return

        try:
            import pylast

            if self.session_key:
                net = pylast.LastFMNetwork(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    session_key=self.session_key,
                    username=self.username,
                )
            else:
                net = pylast.LastFMNetwork(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    username=self.username,
                    password_hash=self.password_hash,
                )

            # Validar conexión consultando el perfil del usuario
            if self.username:
                u = net.get_user(self.username)
                _ = u.get_playcount()

            with self._lock:
                self._network = net
                self._connected = True
                self._status = "connected"
                self._last_error = ""

            log.info("Last.fm conectado exitosamente como %s", self.username or "usuario")
            self._flush_pending_scrobbles()
        except Exception as e:
            with self._lock:
                self._connected = False
                self._status = "error"
                self._last_error = str(e)
            log.warning("No se pudo conectar a Last.fm: %s", e)

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self.enabled and self._connected and self._network is not None

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def status_summary(self) -> str:
        """Devuelve un texto informativo legible sobre el estado de Last.fm."""
        with self._lock:
            if not self.enabled:
                return "Desactivado en config.toml"
            if self._connected:
                return f"Conectado como {self.username}"
            if self._status == "unconfigured":
                return "Faltan credenciales (api_key / secret / usuario)"
            if self._status == "connecting":
                return "Conectando con Last.fm..."
            return f"Error de conexión: {self._last_error}"

    def get_ui_indicator(self) -> Tuple[str, str]:
        """
        Devuelve (texto, color_tag) para mostrar en la interfaz TUI.
        """
        now = time.time()
        with self._lock:
            if not self.enabled:
                return ("", "")
            if not self._connected:
                if self._status == "unconfigured":
                    return ("󰓇 Last.fm: Sin configurar", "subtext1")
                if self._status == "connecting":
                    return ("󰓇 Last.fm: Conectando...", "peach")
                return ("󰓇 Last.fm: Error", "red")

            # Si acaba de scrobblear en los últimos 4 segundos
            if (now - self._last_scrobble_ts) < 4.0:
                return ("󰓇 Scrobbled ✓", "green")

            if self._scrobbled:
                return ("󰓇 Last.fm: Sincronizado", "subtext1")

            if self._current_track:
                return ("󰓇 Last.fm: Escuchando", "peach")

            return ("󰓇 Last.fm: Conectado", "subtext1")

    def on_track_started(self, track: Dict[str, Any]) -> None:
        """Llamado cuando arranca una nueva canción."""
        with self._lock:
            self._current_track = track
            self._track_start_time = int(time.time())
            self._scrobbled = False

        if not self.is_connected:
            return

        artist = str(track.get("artist") or "")
        title = str(track.get("name") or "")
        album = str(track.get("album") or "")
        dur = float(track.get("duration") or 0)

        def _now_playing_worker():
            try:
                with self._lock:
                    net = self._network
                if net and artist and title:
                    net.update_now_playing(
                        artist=artist,
                        title=title,
                        album=album or None,
                        duration=int(dur) if dur > 0 else None,
                    )
                    log.debug("Last.fm Now Playing actualizado: %s - %s", artist, title)
            except Exception as e:
                log.debug("Error actualizando Now Playing en Last.fm: %s", e)

        threading.Thread(target=_now_playing_worker, daemon=True).start()

    def update(self, position: float, duration: float) -> None:
        """
        Llamado en cada tick de reproducción.
        Evalúa las reglas oficiales de Last.fm para scrobblear:
        1. Duración mínima de la pista >= 30 segundos.
        2. La posición escuchada alcanza al menos el 50% de la pista o 240 segundos (4 min).
        3. Se scrobblea una sola vez por reproducción.
        """
        with self._lock:
            if not self._current_track or self._scrobbled:
                return
            if duration < 30.0:
                return

            threshold = min(duration * 0.5, 240.0)
            if position < threshold:
                return

            # Marcamos scrobbled inmediatamente para evitar duplicados
            self._scrobbled = True
            track_copy = dict(self._current_track)
            start_ts = self._track_start_time

        self._submit_scrobble(track_copy, start_ts)

    def _submit_scrobble(self, track: Dict[str, Any], start_ts: int) -> None:
        """Envía el scrobble a Last.fm en segundo plano."""
        artist = str(track.get("artist") or "")
        title = str(track.get("name") or "")
        album = str(track.get("album") or "")
        dur = int(float(track.get("duration") or 0))

        if not (artist and title):
            return

        payload = {
            "artist": artist,
            "title": title,
            "album": album or None,
            "timestamp": start_ts if start_ts > 0 else int(time.time()),
            "duration": dur if dur > 0 else None,
        }

        def _scrobble_worker():
            with self._lock:
                net = self._network
            if not net:
                with self._lock:
                    self._pending_scrobbles.append(payload)
                return

            try:
                net.scrobble(**payload)
                with self._lock:
                    self._last_scrobble_ts = time.time()
                    self._last_scrobbled_title = f"{artist} - {title}"
                log.info("Last.fm Scrobbled con éxito: %s - %s", artist, title)
            except Exception as e:
                log.warning("Fallo al scrobblear '%s - %s': %s. Guardando en cola de reintento.", artist, title, e)
                with self._lock:
                    self._pending_scrobbles.append(payload)

        threading.Thread(target=_scrobble_worker, daemon=True).start()

    def _flush_pending_scrobbles(self) -> None:
        """Reintenta scrobbles fallidos acumulados si la conexión volvió."""
        with self._lock:
            if not self._pending_scrobbles or not self._network:
                return
            to_flush = list(self._pending_scrobbles)
            self._pending_scrobbles.clear()

        def _flush_worker():
            with self._lock:
                net = self._network
            if not net:
                with self._lock:
                    self._pending_scrobbles.extend(to_flush)
                return

            remaining = []
            for item in to_flush:
                try:
                    net.scrobble(**item)
                    log.info("Scrobble pendiente enviado: %s - %s", item.get("artist"), item.get("title"))
                except Exception:
                    remaining.append(item)
            if remaining:
                with self._lock:
                    self._pending_scrobbles.extend(remaining)

        threading.Thread(target=_flush_worker, daemon=True).start()


def test_lastfm_credentials(cfg: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """
    Función de utilidad para probar credenciales directamente desde CLI.
    Devuelve (True, "Mensaje de éxito") o (False, "Detalle del error").
    """
    if cfg is None:
        cfg = config.get_lastfm_config()

    username = str(cfg.get("username", "")).strip()
    api_key = str(cfg.get("api_key", "")).strip()
    api_secret = str(cfg.get("api_secret", "")).strip()
    session_key = str(cfg.get("session_key", "")).strip()
    password_hash = str(cfg.get("password_hash", "")).strip()
    password = str(cfg.get("password", "")).strip()

    if password and not password_hash:
        password_hash = hashlib.md5(password.encode("utf-8")).hexdigest()

    if not api_key or not api_secret:
        return False, "Falta 'api_key' o 'api_secret' en la configuración."

    if not session_key and not (username and password_hash):
        return False, "Se requiere 'session_key' o la combinación de 'username' y 'password'/'password_hash'."

    try:
        import pylast

        if session_key:
            net = pylast.LastFMNetwork(
                api_key=api_key,
                api_secret=api_secret,
                session_key=session_key,
                username=username,
            )
        else:
            net = pylast.LastFMNetwork(
                api_key=api_key,
                api_secret=api_secret,
                username=username,
                password_hash=password_hash,
            )

        if username:
            u = net.get_user(username)
            playcount = u.get_playcount()
            return True, f"¡Conexión exitosa! Usuario: {username} | Scrobbles totales: {playcount}"
        return True, "¡Conexión con Last.fm autenticada con éxito!"
    except Exception as e:
        return False, f"Error al autenticar con Last.fm: {e}"

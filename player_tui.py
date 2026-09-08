#!/home/luki/.local/share/low-tide/.venv/bin/python
"""
Tidal Player TUI (Serpantinum / Kitty / Hyprland)
Full-screen / Tiling music player with native Kitty high-res album art,
synchronized lyrics (LRC), MPV playback and full MPRIS2 D-Bus integration
for Serpantinum audio controls and media widget.
"""

from __future__ import annotations

import argparse
import asyncio
import atexit
import json
import logging
import os
import random
import re
import select
import signal
import socket
import subprocess
import sys
import termios
import threading
import time
import tty
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure low-tide and quick-tide modules are on sys.path
import glob
SHARE_DIR = os.path.dirname(os.path.abspath(__file__))
LOWTIDE_DIR = os.path.expanduser("~/.local/share/low-tide")
venv_site_pkgs = glob.glob(os.path.join(LOWTIDE_DIR, ".venv", "lib", "python*", "site-packages"))

for p in [SHARE_DIR, LOWTIDE_DIR] + venv_site_pkgs:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

import tidal_backend

# Import dbus-next for native MPRIS2 desktop integration
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, dbus_property, method, signal as dbus_signal
from dbus_next.constants import PropertyAccess
from dbus_next import BusType, Variant

MPV_SOCKET = f"/tmp/tidal-mpv-{os.getpid()}.sock"
PLAYER_SOCKET = "/tmp/tidal-player.sock"
SERP_STATE = os.path.expanduser("~/.local/state/serpantinum")

logging.basicConfig(level=logging.ERROR)
log = logging.getLogger(__name__)


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 6:
        return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    return 200, 200, 200


def get_theme_colors() -> dict[str, str]:
    colors = {
        "base": "#110d11",
        "mantle": "#1f1a1f",
        "crust": "#171217",
        "surface0": "#231e23",
        "surface1": "#2e282e",
        "surface2": "#393338",
        "text": "#eae0e7",
        "subtext0": "#cfc3cd",
        "subtext1": "#988d97",
        "mauve": "#e9b5ef",
        "blue": "#e9b5ef",
        "peach": "#f5b7b0",
        "green": "#d6c0d6",
        "red": "#ffb4ab",
    }
    colors_file = os.path.join(SERP_STATE, "qs_colors.json")
    if os.path.isfile(colors_file):
        try:
            with open(colors_file, "r", encoding="utf-8") as f:
                colors.update(json.load(f))
        except Exception:
            pass
    return colors


THEME = get_theme_colors()

def fg_color(key: str) -> str:
    r, g, b = hex_to_rgb(THEME.get(key, "#ffffff"))
    return f"\033[38;2;{r};{g};{b}m"

def bg_color(key: str) -> str:
    r, g, b = hex_to_rgb(THEME.get(key, "#000000"))
    return f"\033[48;2;{r};{g};{b}m"

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

COLOR_MAUVE = fg_color("mauve")
COLOR_PEACH = fg_color("peach")
COLOR_RED = fg_color("red")
COLOR_TEXT = fg_color("text")
COLOR_SUBTEXT0 = fg_color("subtext0")
COLOR_SUBTEXT1 = fg_color("subtext1")
COLOR_SURFACE2 = fg_color("surface2")
COLOR_GREEN = fg_color("green")


# =====================================================================
# MPRIS2 D-BUS INTERFACES (Integración nativa con Serpantinum Shell)
# =====================================================================

class TidalMprisRoot(ServiceInterface):
    def __init__(self, quit_cb):
        super().__init__("org.mpris.MediaPlayer2")
        self._quit_cb = quit_cb

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":
        return "Tidal Hi-Fi"

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def DesktopEntry(self) -> "s":
        return "tidal-search-gui"

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> "as":
        return []

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> "as":
        return []

    @method()
    def Quit(self):
        self._quit_cb()


class TidalMprisPlayer(ServiceInterface):
    def __init__(self, player):
        super().__init__("org.mpris.MediaPlayer2.Player")
        self.player = player
        self._playback_status = "Stopped"
        self._position = 0
        self._volume = 0.8
        self._metadata: dict = {}

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":
        return self._playback_status

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":
        return self._metadata

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":
        return self._position

    @dbus_property(access=PropertyAccess.READ)
    def Volume(self) -> "d":
        return self._volume

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":
        return True

    @method()
    def PlayPause(self):
        self.player.toggle_pause()

    @method()
    def Play(self):
        if self.player.is_paused:
            self.player.toggle_pause()

    @method()
    def Pause(self):
        if not self.player.is_paused:
            self.player.toggle_pause()

    @method()
    def Next(self):
        self.player.next_track()

    @method()
    def Previous(self):
        self.player.prev_track()

    @method()
    def Stop(self):
        self.player.running = False

    @method()
    def Seek(self, offset_us: "x"):
        self.player.mpv.seek(offset_us / 1_000_000.0)

    @method()
    def SetPosition(self, track_id: "o", pos_us: "x"):
        self.player.mpv.command("set_property", "time-pos", pos_us / 1_000_000.0)


class TidalMprisService:
    def __init__(self, player):
        self.player = player
        self.loop = None
        self.bus = None
        self.player_iface: Optional[TidalMprisPlayer] = None
        self.thread = None

    def start(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

        fut = asyncio.run_coroutine_threadsafe(self._async_setup(), self.loop)
        try:
            fut.result(timeout=3.0)
        except Exception as e:
            log.warning("No se pudo iniciar MPRIS: %s", e)

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _async_setup(self):
        self.bus = await MessageBus(bus_type=BusType.SESSION).connect()
        root_iface = TidalMprisRoot(lambda: setattr(self.player, "running", False))
        self.player_iface = TidalMprisPlayer(self.player)
        self.bus.export("/org/mpris/MediaPlayer2", root_iface)
        self.bus.export("/org/mpris/MediaPlayer2", self.player_iface)
        await self.bus.request_name("org.mpris.MediaPlayer2.tidal")

    def update_track(self, track: dict, cover_path: str = ""):
        if not self.player_iface or not self.loop:
            return
        try:
            raw_id = str(track.get("id") or "0")
            clean_id = "".join(c if (c.isalnum() or c == "_") else "_" for c in raw_id)
            if not clean_id:
                clean_id = "0"
            title = str(track.get("name") or "")
            artist = str(track.get("artist") or "")
            album = str(track.get("album") or "")
            dur = track.get("duration") or 0
            try:
                duration_us = int(float(dur) * 1_000_000)
            except Exception:
                duration_us = 0

            art_url = f"file://{cover_path}" if (cover_path and os.path.isfile(cover_path)) else str(track.get("cover_url") or "")

            meta = {
                "mpris:trackid": Variant("o", f"/org/mpris/MediaPlayer2/track/{clean_id}"),
                "mpris:length": Variant("x", duration_us),
                "mpris:artUrl": Variant("s", art_url),
                "xesam:title": Variant("s", title),
                "xesam:artist": Variant("as", [artist] if artist else []),
                "xesam:album": Variant("s", album),
            }
            self.player_iface._metadata = meta
            self.player_iface._playback_status = "Playing"
            self.loop.call_soon_threadsafe(
                self.player_iface.emit_properties_changed,
                {"Metadata": meta, "PlaybackStatus": "Playing"}
            )
        except Exception as e:
            log.warning("Error actualizando metadatos MPRIS: %s", e)

    def update_playback_status(self, is_paused: bool):
        if not self.player_iface or not self.loop:
            return
        status = "Paused" if is_paused else "Playing"
        self.player_iface._playback_status = status
        self.loop.call_soon_threadsafe(
            self.player_iface.emit_properties_changed,
            {"PlaybackStatus": status}
        )

    def update_position(self, pos_s: float):
        if not self.player_iface:
            return
        self.player_iface._position = int(pos_s * 1_000_000)

    def update_volume(self, volume_pct: int):
        if not self.player_iface or not self.loop:
            return
        vol = float(volume_pct / 100.0)
        self.player_iface._volume = vol
        self.loop.call_soon_threadsafe(
            self.player_iface.emit_properties_changed,
            {"Volume": vol}
        )

    def stop(self):
        if self.bus and self.loop:
            async def _disconnect():
                try:
                    self.bus.disconnect()
                except Exception:
                    pass
            asyncio.run_coroutine_threadsafe(_disconnect(), self.loop)


# =====================================================================
# MOTOR DE AUDIO MPV (Control por Socket IPC)
# =====================================================================

class MpvProcess:
    """Manages MPV subprocess and IPC socket."""

    def __init__(self, sock_path: str):
        self.sock_path = sock_path
        self.proc: Optional[subprocess.Popen] = None
        self.sock: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self.start()

    def start(self):
        if os.path.exists(self.sock_path):
            try:
                os.unlink(self.sock_path)
            except OSError:
                pass

        cmd = [
            "mpv",
            "--no-video",
            "--idle=yes",
            "--load-scripts=no",
            f"--input-ipc-server={self.sock_path}",
            "--really-quiet",
            "--gapless-audio=yes",
            "--demuxer-lavf-o=protocol_whitelist=[file,crypto,data,https,tls,tcp]",
        ]
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        for _ in range(50):
            if os.path.exists(self.sock_path):
                break
            time.sleep(0.05)

        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(0.4)
            self.sock.connect(self.sock_path)
        except Exception as e:
            log.error("No se pudo conectar al socket IPC de MPV: %s", e)

    def command(self, *args) -> Any:
        with self._lock:
            if not self.sock:
                return None
            try:
                payload = json.dumps({"command": list(args)}) + "\n"
                self.sock.sendall(payload.encode("utf-8"))
                buf = ""
                while True:
                    chunk = self.sock.recv(4096).decode("utf-8")
                    if not chunk:
                        break
                    buf += chunk
                    for line in buf.splitlines():
                        try:
                            data = json.loads(line)
                            if "data" in data or "error" in data:
                                return data.get("data")
                        except Exception:
                            pass
            except Exception:
                return None

    def load_file(self, url: str):
        return self.command("loadfile", url, "replace")

    def toggle_pause(self):
        return self.command("cycle", "pause")

    def seek(self, seconds: float):
        return self.command("seek", seconds, "relative")

    def set_volume(self, vol: int):
        return self.command("set_property", "volume", max(0, min(100, vol)))

    def get_property(self, prop: str) -> Any:
        return self.command("get_property", prop)

    def stop(self):
        with self._lock:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1.0)
            except Exception:
                pass
            self.proc = None
        if os.path.exists(self.sock_path):
            try:
                os.unlink(self.sock_path)
            except OSError:
                pass



# =====================================================================
# VISUALIZADOR DE AUDIO TIPO CAVA (Simulación física de espectro)
# =====================================================================

class CavaVisualizer:
    """Cava-style physics audio visualizer filling available vertical space."""

    BLOCKS = "  ▂▃▄▅▆▇█"

    def __init__(self, num_bars: int = 18, max_height: int = 8):
        self.num_bars = num_bars
        self.max_height = max_height
        self.heights = [0.0] * num_bars
        self.targets = [0.0] * num_bars
        self.bar_peak = [0.0] * num_bars
        self.fall_vel = [0.0] * num_bars
        self.pk_height = [0.0] * num_bars
        self.pk_hold = [0.0] * num_bars
        self.pk_vel = [0.0] * num_bars
        self.bpm = 120.0
        self.beat_phase = 0.0
        self.beat_count = 0
        self.energy = 0.8
        self.energy_target = 0.8
        self.ceilings = [max(0.4, 1.0 - (i / max(1, num_bars)) * 0.55) for i in range(num_bars)]
        self.rise_rates = [0.45 + (i / max(1, num_bars)) * 0.20 for i in range(num_bars)]
        self._last_real_audio = 0.0

    def resize(self, num_bars: int, max_height: int):
        if num_bars != self.num_bars or max_height != self.max_height:
            self.num_bars = max(4, num_bars)
            self.max_height = max(2, max_height)
            self.heights = [0.0] * self.num_bars
            self.targets = [0.0] * self.num_bars
            self.bar_peak = [0.0] * self.num_bars
            self.fall_vel = [0.0] * self.num_bars
            self.pk_height = [0.0] * self.num_bars
            self.pk_hold = [0.0] * self.num_bars
            self.pk_vel = [0.0] * self.num_bars
            self.ceilings = [max(0.4, 1.0 - (i / max(1, self.num_bars)) * 0.55) for i in range(self.num_bars)]
            self.rise_rates = [0.45 + (i / max(1, self.num_bars)) * 0.20 for i in range(self.num_bars)]

    def set_bpm(self, bpm: float | None):
        self.bpm = float(bpm) if bpm and 50 <= bpm <= 220 else 120.0

    def feed_real_spectrum(self, norm_values: list[float]):
        """Alimenta las bandas de frecuencia reales capturadas por PipeWire/Cava."""
        if not norm_values:
            return
        m = len(norm_values)
        n = self.num_bars
        # Re-muestreo adaptativo a la cantidad de barras actual
        for i in range(n):
            idx = min(m - 1, int(i * m / n))
            val = norm_values[idx]
            self.targets[i] = val * self.max_height
        self._last_real_audio = time.time()

    def tick(self, is_paused: bool, dt: float = 0.028):
        dt = max(0.005, min(0.1, dt))
        if is_paused:
            decay = max(0.0, 1.0 - 4.0 * dt)
            for i in range(self.num_bars):
                self.targets[i] = 0.0
                self.heights[i] = max(0.0, self.heights[i] * decay)
                self.pk_height[i] = max(0.0, self.pk_height[i] * decay)
            return

        has_real = (time.time() - self._last_real_audio < 0.35)

        if not has_real:
            # Fallback procedural basado en BPM si no hay audio o hay silencio
            beat_interval = 60.0 / self.bpm
            self.beat_phase += dt
            if self.beat_phase >= beat_interval:
                self.beat_phase -= beat_interval
                self.beat_count += 1
                self._on_beat()

            if random.random() < (1.4 * dt):
                self.energy_target = random.uniform(0.65, 1.2)
            self.energy += (self.energy_target - self.energy) * min(1.0, 3.5 * dt)

            target_decay = max(0.0, 1.0 - 1.2 * dt)
            for i in range(self.num_bars):
                prob = (1.8 + (i / max(1, self.num_bars)) * 1.2) * dt
                if random.random() < prob:
                    c = self.max_height * self.ceilings[i] * self.energy
                    self.targets[i] = random.uniform(c * 0.25, c)
                self.targets[i] *= target_decay

        for i in range(self.num_bars):
            if self.targets[i] > self.heights[i]:
                rise = min(1.0, self.rise_rates[i] * (dt / 0.028))
                self.heights[i] += (self.targets[i] - self.heights[i]) * rise
                self.bar_peak[i] = self.heights[i]
                self.fall_vel[i] = 0.0

                if self.heights[i] > self.pk_height[i]:
                    self.pk_height[i] = self.heights[i]
                    self.pk_hold[i] = 0.25
                    self.pk_vel[i] = 0.0
            else:
                self.fall_vel[i] += 1.5 * dt
                norm = (self.bar_peak[i] / self.max_height) if self.max_height else 0.0
                new_norm = norm * max(0.0, 1.0 - (self.fall_vel[i] ** 2) * 2.4)
                self.heights[i] = max(0.0, new_norm * self.max_height)

            if self.pk_hold[i] > 0.0:
                self.pk_hold[i] -= dt
            else:
                self.pk_vel[i] += 1.3 * dt
                self.pk_height[i] -= (self.pk_vel[i] ** 2) * 2.2 * self.max_height * (dt * 10.0)
                if self.pk_height[i] < self.heights[i]:
                    self.pk_height[i] = self.heights[i]


    def _on_beat(self):
        for i in range(min(4, self.num_bars)):
            self.targets[i] = self.max_height * self.ceilings[i] * random.uniform(0.85, 1.0)
        if (self.beat_count % 2) == 0:
            mid_start = self.num_bars // 4
            mid_end = (3 * self.num_bars) // 4
            for i in range(mid_start, min(mid_end, self.num_bars)):
                self.targets[i] = self.max_height * self.ceilings[i] * random.uniform(0.65, 0.95)

    def _smooth_monstercat(self, values: list[float]) -> list[float]:
        out = list(values)
        factor = 1.6
        for i in range(self.num_bars):
            for j in range(self.num_bars):
                dist = abs(i - j)
                if dist > 0:
                    contrib = values[j] / (factor ** dist)
                    if contrib > out[i]:
                        out[i] = contrib
        return out

    def render_rows(self) -> list[str]:
        smooth = self._smooth_monstercat(self.heights)
        rendered_lines = []

        for row in range(self.max_height - 1, -1, -1):
            row_parts = []
            t = row / max(1, self.max_height - 1)
            if t < 0.5:
                col_code = COLOR_MAUVE
            elif t < 0.8:
                col_code = COLOR_PEACH
            else:
                col_code = COLOR_RED

            for b in range(self.num_bars):
                h = smooth[b]
                pk = self.pk_height[b]
                pk_row = int(pk)

                if row == pk_row and pk > h + 0.35:
                    row_parts.append(f"{BOLD}{COLOR_TEXT}▔▔{RESET} ")
                elif h >= row + 1:
                    row_parts.append(f"{col_code}██{RESET} ")
                elif h > row:
                    frac = h - row
                    idx = max(1, min(8, int(frac * 8)))
                    ch = self.BLOCKS[idx]
                    row_parts.append(f"{col_code}{ch}{ch}{RESET} ")
                else:
                    row_parts.append("   ")
            rendered_lines.append("".join(row_parts))

        return rendered_lines


class CavaPipewireReader:
    """Captura el espectro de audio real desde PipeWire usando Cava en modo raw."""
    def __init__(self, bars: int = 24):
        self.bars = bars
        self.running = True
        self.proc: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.latest_norm: list[float] = [0.0] * bars
        self.last_update = 0.0
        self._lock = threading.Lock()
        self.start()

    def start(self):
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def _read_loop(self):
        cfg = f"""
[general]
bars = {self.bars}
framerate = 35

[input]
method = pipewire
source = auto

[output]
method = raw
raw_target = /dev/stdout
data_format = ascii
ascii_max_range = 100
bar_delimiter = 59
frame_delimiter = 10
"""
        try:
            self.proc = subprocess.Popen(
                ["cava", "-p", "/dev/stdin"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True
            )
            self.proc.stdin.write(cfg)
            self.proc.stdin.close()

            while self.running and self.proc and self.proc.poll() is None:
                line = self.proc.stdout.readline()
                if not line:
                    break
                parts = [p for p in line.strip().split(";") if p]
                if parts:
                    vals = [min(1.0, max(0.0, float(x) / 100.0)) for x in parts[:self.bars]]
                    if len(vals) < self.bars:
                        vals += [0.0] * (self.bars - len(vals))
                    with self._lock:
                        self.latest_norm = vals
                        self.last_update = time.time()
        except Exception as e:
            log.warning("Cava pipewire reader no disponible: %s", e)

    def get_spectrum(self) -> tuple[list[float], float]:
        with self._lock:
            return list(self.latest_norm), self.last_update

    def stop(self):
        self.running = False
        if self.proc:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=0.5)
            except Exception:
                pass
            self.proc = None


# =====================================================================
# REPRODUCTOR TUI (Kitty Graphics + Letras + Serpantinum Theme)
# =====================================================================

class TidalPlayerTUI:
    def __init__(self, initial_type: str = "track", initial_id: Optional[Any] = None, initial_start_idx: int = 0):
        self.mpv = MpvProcess(MPV_SOCKET)
        self.running = True
        self.queue: List[Dict[str, Any]] = []
        self.current_idx: int = 0
        self.current_track: Optional[Dict[str, Any]] = None
        self.current_cover_path: str = ""
        self._displayed_cover: Any = None
        self.lyrics_synced: List[Dict[str, Any]] = []
        self.lyrics_plain: List[str] = []
        self.is_paused: bool = False
        self.volume: int = 80
        self.position: float = 0.0
        self.duration: float = 0.0
        self.old_term_settings = None
        self.last_cols = 0
        self.last_lines = 0
        self.needs_full_redraw = True
        self._cmd_lock = threading.Lock()
        self.visualizer = CavaVisualizer()
        self.cava_reader = CavaPipewireReader(bars=24)
        self._cached_badge = "[ FLAC • 1411 kbps ]"
        self._last_badge_check = 0.0
        self._last_mpv_poll = 0.0

        # Iniciar servicio MPRIS2 D-Bus
        self.mpris = TidalMprisService(self)
        self.mpris.start()

        # Configurar volumen inicial
        self.mpv.set_volume(self.volume)
        self.mpris.update_volume(self.volume)

        # Iniciar servidor IPC para recibir selecciones al vuelo desde el buscador
        self.ipc_thread = threading.Thread(target=self._ipc_server_loop, daemon=True)
        self.ipc_thread.start()

        # Cargar selección inicial
        if initial_id:
            self.load_selection(initial_type, initial_id, initial_start_idx)

    def _ipc_server_loop(self):
        """Escucha comandos desde tidal-search-gui para cambiar canciones/álbumes/playlists al vuelo."""
        if os.path.exists(PLAYER_SOCKET):
            try:
                os.unlink(PLAYER_SOCKET)
            except OSError:
                pass

        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(PLAYER_SOCKET)
        server.listen(5)
        server.settimeout(0.5)

        while self.running:
            try:
                conn, _ = server.accept()
                conn.settimeout(1.0)
                data = conn.recv(4096).decode("utf-8")
                conn.close()
                if not data:
                    continue
                for line in data.splitlines():
                    msg = json.loads(line)
                    if msg.get("action") == "play":
                        sel_type = msg.get("type", "track")
                        sel_id = msg.get("id")
                        start_idx = int(msg.get("start_idx", 0))
                        threading.Thread(
                            target=self.load_selection,
                            args=(sel_type, sel_id, start_idx),
                            daemon=True
                        ).start()
            except socket.timeout:
                continue
            except Exception:
                pass

        try:
            server.close()
            if os.path.exists(PLAYER_SOCKET):
                os.unlink(PLAYER_SOCKET)
        except Exception:
            pass

    def load_selection(self, item_type: str, item_id: Any, start_idx: int = 0):
        with self._cmd_lock:
            if item_type == "album":
                tracks = tidal_backend.get_album_tracks(int(item_id))
                if tracks:
                    self.queue = tracks
                    self.current_idx = max(0, min(start_idx, len(tracks) - 1))
                    self.play_track(self.queue[self.current_idx])
            elif item_type == "playlist":
                tracks = tidal_backend.get_playlist_tracks(str(item_id))
                if tracks:
                    self.queue = tracks
                    self.current_idx = max(0, min(start_idx, len(tracks) - 1))
                    self.play_track(self.queue[self.current_idx])
            else:
                track = tidal_backend.get_track_details(int(item_id))
                if track:
                    self.queue = [track]
                    self.current_idx = 0
                    self.play_track(track)

    def play_track(self, track: Dict[str, Any]):
        self.current_track = track
        self.position = 0.0
        self.duration = float(track.get("duration", 0))
        self.is_paused = False
        self.needs_full_redraw = True
        self._displayed_cover = None
        self._last_badge_check = 0.0
        self._last_mpv_poll = 0.0

        # Obtener stream URL o manifiesto DASH
        stream_url = tidal_backend.get_track_stream_url(track.get("raw_obj") or track.get("id"))
        if stream_url:
            self.mpv.load_file(stream_url)

        # Iniciar descarga de carátula
        cover_url = track.get("cover_url")
        key = track.get("album_id") or track.get("id")

        def _cover_downloader():
            c_path = tidal_backend.download_cover(cover_url, key)
            self.current_cover_path = c_path
            # Actualizar MPRIS con la carátula local
            self.mpris.update_track(track, c_path)

        threading.Thread(target=_cover_downloader, daemon=True).start()

        # Notificar a MPRIS inicialmente
        self.mpris.update_track(track, "")

        # Obtener letras en segundo plano (Tidal con fallback automático a LRCLIB)
        self.lyrics_synced = []
        self.lyrics_plain = []
        t_id = track.get("id")
        t_raw = track.get("raw_obj")
        t_title = track.get("name", "")
        t_artist = track.get("artist", "")
        t_album = track.get("album", "")
        t_dur = track.get("duration", 0.0)

        def _lyrics_worker():
            try:
                plain, synced = tidal_backend.get_track_lyrics(
                    t_raw or t_id,
                    title=t_title,
                    artist=t_artist,
                    album=t_album,
                    duration=t_dur
                )
                if self.current_track and str(self.current_track.get("id")) == str(t_id):
                    self.lyrics_synced = synced
                    self.lyrics_plain = [l.strip() for l in plain.splitlines() if l.strip()] if plain else []
            except Exception as e:
                log.warning("Error cargando letras: %s", e)

        threading.Thread(target=_lyrics_worker, daemon=True).start()

        # Actualizar BPM en el visualizador
        bpm = getattr(track.get("raw_obj"), "bpm", None) or 120.0
        self.visualizer.set_bpm(bpm)

    def toggle_pause(self):
        self.mpv.toggle_pause()
        self.is_paused = not self.is_paused
        self.mpris.update_playback_status(self.is_paused)

    def next_track(self):
        with self._cmd_lock:
            if self.queue and self.current_idx < len(self.queue) - 1:
                self.current_idx += 1
                self.play_track(self.queue[self.current_idx])

    def prev_track(self):
        with self._cmd_lock:
            if self.queue:
                if self.position > 3.0:
                    self.mpv.seek(-self.position)
                elif self.current_idx > 0:
                    self.current_idx -= 1
                    self.play_track(self.queue[self.current_idx])

    def setup_terminal(self):
        try:
            self.old_term_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        except Exception:
            pass
        sys.stdout.write("\033[?25l\033[2J\033[H")
        sys.stdout.flush()

    def restore_terminal(self):
        try:
            sys.stdout.flush()
            subprocess.run(["kitten", "icat", "--clear-all"], stdout=None, stderr=subprocess.DEVNULL, check=False)
            sys.stdout.flush()
        except Exception:
            pass
        sys.stdout.write("\033[?25h\033[0m\033[2J\033[H")
        sys.stdout.flush()
        if self.old_term_settings:
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_term_settings)
            except Exception:
                pass

    def render_kitty_art(self, art_x: int, art_y: int, art_w: int, art_h: int):
        if not self.current_cover_path or not os.path.isfile(self.current_cover_path):
            return
        place_arg = f"{art_w}x{art_h}@{art_x}x{art_y}"
        try:
            sys.stdout.flush()
            subprocess.run(
                ["kitten", "icat", "--place", place_arg, "--align", "center", self.current_cover_path],
                stdout=None,
                stderr=subprocess.DEVNULL,
                check=False
            )
            sys.stdout.flush()
        except Exception as e:
            log.error("Error mostrando carátula: %s", e)

    def get_quality_badge(self) -> tuple[str, int]:
        now = time.time()
        if (now - self._last_badge_check < 2.5) and getattr(self, "_cached_badge_tuple", None):
            return self._cached_badge_tuple

        self._last_badge_check = now
        track = self.current_track or {}
        raw_q = str(track.get("quality", "LOSSLESS")).upper()
        is_hires = "HI_RES" in raw_q or "HIRES" in raw_q or "MAX" in raw_q

        br = self.mpv.get_property("audio-bitrate")
        codec = self.mpv.get_property("audio-codec-name") or "FLAC"
        params = self.mpv.get_property("audio-params") or {}
        samplerate = params.get("samplerate", 0) if isinstance(params, dict) else 0

        # Colores oficiales de Tidal con fondito sutil translúcido (igual que Super + T):
        # MAX / Hi-Res: Gold (#f5c542) sobre fondo oscuro dorado
        # FLAC / Lossless: Cyan (#00d2ff) sobre fondo oscuro cyan
        # Atmos: Purple (#bb86fc) sobre fondo oscuro púrpura
        # Normal/Low: Gray (#a6adc8) sobre fondo gris oscuro
        if is_hires:
            q_name = "MAX" if "MAX" in raw_q else "HI-RES"
            q_fg = "\033[38;2;245;197;66m"
            q_bg = "\033[48;2;48;38;14m"
        elif "LOW" in raw_q:
            q_name = "LOW"
            q_fg = "\033[38;2;166;173;200m"
            q_bg = "\033[48;2;36;38;46m"
        elif "ATMOS" in raw_q:
            q_name = "ATMOS"
            q_fg = "\033[38;2;187;134;252m"
            q_bg = "\033[48;2;38;24;54m"
        elif raw_q in ["LOSSLESS", "FLAC"] or "FLAC" in str(codec).upper():
            q_name = "FLAC"
            q_fg = "\033[38;2;0;210;255m"
            q_bg = "\033[48;2;0;42;54m"
        else:
            q_name = "HIGH" if "HIGH" in raw_q else str(codec).upper()
            q_fg = "\033[38;2;116;199;236m"
            q_bg = "\033[48;2;22;42;52m"

        # Formato sin corchetes ni kbps, píldora limpia con fondito de color igual a Super+T
        plain = f" {q_name} "
        styled = f"{q_bg}{q_fg} {q_name} {RESET}"

        self._cached_badge_tuple = (styled, len(plain))
        return self._cached_badge_tuple

    def draw_screen(self, dt: float = 0.028):
        try:
            cols, lines = os.get_terminal_size()
        except Exception:
            cols, lines = 120, 36

        resized = (cols != self.last_cols or lines != self.last_lines)
        if resized:
            self.last_cols = cols
            self.last_lines = lines
            self.needs_full_redraw = True
            try:
                subprocess.run(["kitten", "icat", "--clear"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            except Exception:
                pass

        buf: list[str] = []
        w = buf.append

        # Diseño reactivo para Hyprland / tiling dinámico:
        # A partir de 66 columnas hay espacio para dos columnas (reproductor + letras sincronizadas).
        # Con menos de 66 columnas, el reproductor usa ancho completo sin deformar controles ni fuentes.
        show_lyrics = (cols >= 66)

        if show_lyrics:
            if cols >= 120:
                left_width = min(68, max(48, int(cols * 0.52)))
            elif cols >= 90:
                left_width = min(56, max(42, int(cols * 0.50)))
            else:
                left_width = min(46, max(36, int(cols * 0.48)))
            divider_col = left_width + 1
            right_col = left_width + 3
            right_width = max(10, cols - right_col - 1)
        else:
            left_width = max(24, cols - 2)
            divider_col = None
            right_col = None
            right_width = 0

        # Helper para limpiar sólo el ancho del módulo izquierdo sin borrar el divisor ni la columna derecha
        def clear_left(r: int):
            w(f"\033[{r};2H{' ' * (left_width - 1)}")

        # Configuración reactiva: achicar CAVA y bajar el reproductor para darle máximo espacio a la carátula
        if lines >= 32:
            target_cava_h = 4
            has_gap = True
            show_cava = True
        elif lines >= 25:
            target_cava_h = 3
            has_gap = True
            show_cava = True
        elif lines >= 20:
            target_cava_h = 3
            has_gap = False
            show_cava = True
        else:
            target_cava_h = 0
            has_gap = False
            show_cava = False

        # Espacio reservado para la barra de atajos inferior
        bottom_reserved = 3 if lines >= 20 else 1

        if show_cava and target_cava_h > 0:
            vis_bottom = lines - bottom_reserved
            vis_top = vis_bottom - target_cava_h + 1
            vis_height = target_cava_h
            status_row = vis_top - 2  # Dejar 1 línea de respiro antes de CAVA
        else:
            vis_bottom = 0
            vis_top = 0
            vis_height = 0
            status_row = lines - bottom_reserved - 1

        # El reproductor se posiciona más abajo (sobre CAVA):
        # status_row: Controles (Play/Pausa y Pista xx/xx)
        # prog_row: Barra de progreso (00:00 ━━━●─── 03:45)
        # gap_row: Respiro visual
        # artist_row: Artista y Badge
        # title_row: Nombre de la canción
        prog_row = status_row - 1
        if has_gap and prog_row - 3 >= 2:
            gap_row = prog_row - 1
            artist_row = prog_row - 2
            title_row = prog_row - 3
        else:
            has_gap = False
            gap_row = None
            artist_row = prog_row - 1
            title_row = prog_row - 2

        # La carátula se agranda ocupando todo el espacio ganado arriba
        art_y = 2 if lines >= 20 else 1
        gap_art_text = 2 if (lines >= 28) else 1
        max_possible_art_h = title_row - gap_art_text - art_y

        if max_possible_art_h >= 5:
            # Mantener proporción cuadrada ~1:2 en celdas de terminal
            max_h_by_width = int((left_width - 4) / 2.05)
            art_h = min(24, max_possible_art_h, max_h_by_width)
            art_w = min(left_width - 4, int(art_h * 2.05))
            art_x = max(2, (left_width - art_w) // 2)
        else:
            art_h = 0
            art_w = 0
            art_x = 2

        if self.needs_full_redraw:
            w("\033_Ga=d,d=A\033\\")  # Eliminar imágenes Kitty previas de inmediato
            w("\033[2J")             # Limpiar pantalla completa
            self.needs_full_redraw = False
            self._displayed_cover = None

        # Renderizar carátula en Kitty si corresponde
        cover_signature = (self.current_cover_path, art_w, art_h, art_x, art_y)
        if art_h > 0 and self.current_cover_path and os.path.isfile(self.current_cover_path):
            if self._displayed_cover != cover_signature:
                if buf:
                    sys.stdout.write("".join(buf))
                    sys.stdout.flush()
                    buf.clear()
                self.render_kitty_art(art_x, art_y, art_w, art_h)
                self._displayed_cover = cover_signature
        elif art_h == 0 and self._displayed_cover is not None:
            try:
                subprocess.run(["kitten", "icat", "--clear"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            except Exception:
                pass
            self._displayed_cover = None

        # Limpiar filas entre la carátula y el título de la canción
        for r in range(art_y + art_h, title_row):
            clear_left(r)

        # ================= METADATOS (COLUMNA IZQUIERDA) =================
        track = self.current_track or {}
        title = track.get("name", "Ninguna canción cargada")
        artist = track.get("artist", "Abre el menú de búsqueda (SUPER + T)")
        styled_badge, badge_len = self.get_quality_badge()

        # Fila 1: Nombre del tema (arriba en negrita, jerarquía principal completa)
        clear_left(title_row)
        w(f"\033[{title_row};2H{BOLD}{COLOR_TEXT}{title[:left_width-4]}{RESET}")

        pos_str = tidal_backend.format_duration(self.position)
        dur_str = tidal_backend.format_duration(self.duration)
        bar_len = max(6, left_width - 16)
        ratio = (self.position / self.duration) if self.duration > 0 else 0.0
        filled = int(ratio * bar_len)
        bar_str = "━" * filled + "●" + "─" * max(0, bar_len - filled - 1)

        # La duración termina en right_edge (margen derecho simétrico de la columna izquierda)
        dur_start_col = 4 + len(pos_str) + bar_len
        right_edge = dur_start_col + len(dur_str) - 1

        # Fila 2: Artista a la izquierda y Badge de calidad a la derecha alineado con la duración
        badge_col = max(2, right_edge - badge_len + 1)
        max_artist_len = max(6, badge_col - 4)

        clear_left(artist_row)
        w(f"\033[{artist_row};2H{COLOR_SUBTEXT1}{artist[:max_artist_len]}{RESET}")
        w(f"\033[{artist_row};{badge_col}H{styled_badge}")

        if gap_row:
            clear_left(gap_row)

        # Fila de Barra de progreso
        clear_left(prog_row)
        w(f"\033[{prog_row};2H{COLOR_SUBTEXT1}{pos_str} {COLOR_MAUVE}{bar_str} {COLOR_SUBTEXT1}{dur_str}{RESET}")

        # Fila de Controles de reproducción centrados y contador de pista alineado a la derecha
        status_icon = f"{BOLD}{COLOR_PEACH}⏸{RESET}" if self.is_paused else f"{BOLD}{COLOR_MAUVE}▶{RESET}"
        queue_pos = f"Pista {self.current_idx + 1}/{len(self.queue)}" if self.queue else ""

        clear_left(status_row)
        center_col = max(2, left_width // 2)
        w(f"\033[{status_row};{center_col}H{status_icon}")

        if queue_pos:
            q_text = queue_pos if left_width >= 42 else f"{self.current_idx + 1}/{len(self.queue)}"
            queue_col = max(center_col + 4, right_edge - len(q_text) + 1)
            w(f"\033[{status_row};{queue_col}H{COLOR_SUBTEXT1}{q_text}{RESET}")

        # Fila separadora antes del visualizador
        clear_left(status_row + 1)

        # ================= VISUALIZADOR DE AUDIO (TIPO CAVA) =================
        if show_cava and vis_height >= 2 and left_width >= 16:
            num_bars = max(4, (left_width - 6) // 3)
            total_bars_width = num_bars * 3
            vis_x = max(2, (left_width - total_bars_width) // 2 + 2)

            # Obtener espectro real capturado por Cava desde PipeWire
            real_spec, last_ts = self.cava_reader.get_spectrum()
            if (time.time() - last_ts < 0.35) and not self.is_paused:
                self.visualizer.feed_real_spectrum(real_spec)

            self.visualizer.resize(num_bars, vis_height)
            self.visualizer.tick(is_paused=self.is_paused, dt=dt)
            vis_lines = self.visualizer.render_rows()

            for i, line_str in enumerate(vis_lines):
                target_r = vis_top + i
                clear_left(target_r)
                w(f"\033[{target_r};{vis_x}H{line_str}")

        # Guía de teclas ubicada abajo a la izquierda en la esquina (reactiva a tamaño de pantalla)
        if lines >= 20:
            clear_left(lines - 2)
            w(f"\033[{lines - 2};2H{COLOR_SURFACE2}{'─' * (left_width - 2)}{RESET}")
            clear_left(lines - 1)
            if left_width >= 50:
                guide_str = f"{COLOR_SUBTEXT1}[Espacio] {COLOR_TEXT}Pausa  {COLOR_SUBTEXT1}[←/→] {COLOR_TEXT}±10s  {COLOR_SUBTEXT1}[n/p] {COLOR_TEXT}Pistas  {COLOR_SUBTEXT1}[q] {COLOR_TEXT}Salir{RESET}"
            elif left_width >= 36:
                guide_str = f"{COLOR_SUBTEXT1}[␣] {COLOR_TEXT}Pausa  {COLOR_SUBTEXT1}[←/→] {COLOR_TEXT}±10s  {COLOR_SUBTEXT1}[n/p] {COLOR_TEXT}Cola  {COLOR_SUBTEXT1}[q] {COLOR_TEXT}Salir{RESET}"
            else:
                guide_str = f"{COLOR_SUBTEXT1}[␣] {COLOR_TEXT}Pausa  {COLOR_SUBTEXT1}[q] {COLOR_TEXT}Salir{RESET}"
            w(f"\033[{lines - 1};2H{guide_str[:left_width-2]}")

        # ================= LETRAS (COLUMNA DERECHA) =================
        if show_lyrics and right_col and right_width:
            w(f"\033[1;{right_col}H\033[K")
            w(f"\033[2;{right_col}H\033[K")

            start_row = 2
            lyric_lines_avail = lines - 4

            if self.lyrics_synced:
                active_idx = 0
                for i, item in enumerate(self.lyrics_synced):
                    if item["timestamp"] <= self.position:
                        active_idx = i
                    else:
                        break

                start_idx = active_idx - (lyric_lines_avail // 2)
                for offset in range(lyric_lines_avail):
                    curr_row = start_row + offset
                    item_idx = start_idx + offset
                    w(f"\033[{curr_row};{right_col}H\033[K")

                    if 0 <= item_idx < len(self.lyrics_synced):
                        dist = abs(item_idx - active_idx)

                        # Si está más allá del alcance de la curva, no mostrar nada
                        if dist > 4:
                            continue

                        l_text = self.lyrics_synced[item_idx]["text"]

                        # Efecto de lente circular / cilindro 3D:
                        if dist == 0:
                            style = f"{BOLD}{COLOR_MAUVE}"
                            prefix = " ▶ "
                        elif dist == 1:
                            style = "\033[38;2;234;224;231m"  # Texto principal claro y nítido
                            prefix = "    "
                        elif dist == 2:
                            style = "\033[38;2;195;182;194m"  # Subtexto medio
                            prefix = "     "
                        elif dist == 3:
                            style = "\033[38;2;138;125;137m"  # Atenuado gris
                            prefix = "      "
                        else: # dist == 4
                            style = "\033[38;2;75;64;76m"     # Fundiéndose casi al 100% con el fondo
                            prefix = "       "

                        max_len = max(6, right_width - len(prefix) - 2)
                        if len(l_text) > max_len:
                            l_text = l_text[:max_len - 3] + "..."

                        w(f"{style}{prefix}{l_text}{RESET}")
            elif self.lyrics_plain:
                mid_plain = lyric_lines_avail // 2
                for offset in range(min(lyric_lines_avail, len(self.lyrics_plain))):
                    curr_row = start_row + offset
                    w(f"\033[{curr_row};{right_col}H\033[K")
                    dist = abs(offset - mid_plain)
                    if dist > 4:
                        continue
                    l_text = self.lyrics_plain[offset]
                    if dist <= 1:
                        style = f"{COLOR_TEXT}"
                        prefix = "    "
                    elif dist == 2:
                        style = f"{COLOR_SUBTEXT0}"
                        prefix = "     "
                    elif dist == 3:
                        style = f"{COLOR_SUBTEXT1}"
                        prefix = "      "
                    else: # dist == 4
                        style = "\033[38;2;75;64;76m"
                        prefix = "       "
                    max_len = max(6, right_width - len(prefix) - 2)
                    if len(l_text) > max_len:
                        l_text = l_text[:max_len - 3] + "..."
                    w(f"{style}{prefix}{l_text}{RESET}")
            else:
                mid_r = lines // 2
                w(f"\033[{mid_r - 1};{right_col + 2}H\033[K")
                w(f"{COLOR_SURFACE2}♪  ♫  ♩  ♬  ♪  ♫  ♩  ♬{RESET}")
                w(f"\033[{mid_r};{right_col + 2}H\033[K")
                w(f"{COLOR_SUBTEXT1}No hay letras disponibles para este tema.{RESET}")
                w(f"\033[{mid_r + 1};{right_col + 2}H\033[K")
                w(f"{COLOR_SURFACE2}Disfruta de la calidad de audio Hi-Fi en Tidal.{RESET}")

            # Limpiar filas restantes del margen inferior derecho
            w(f"\033[{lines - 1};{right_col}H\033[K")
            w(f"\033[{lines};{right_col}H\033[K")

            # Dibujar divisor vertical continuo de arriba a abajo en cada frame (sin huecos)
            for r in range(1, lines):
                w(f"\033[{r};{divider_col}H{COLOR_SURFACE2}│{RESET}")

        sys.stdout.write("".join(buf))
        sys.stdout.flush()

    def update_playback_state(self, dt: float = 0.0):
        now = time.time()
        # Interpolate position smoothly between IPC socket queries
        if not self.is_paused and self.position > 0.0:
            self.position += dt

        # Query MPV IPC every 0.25s (4 Hz) to eliminate socket round-trip stalls
        if now - self._last_mpv_poll < 0.25:
            return

        self._last_mpv_poll = now
        pos = self.mpv.get_property("time-pos")
        if pos is not None:
            self.position = float(pos)
            self.mpris.update_position(self.position)

        dur = self.mpv.get_property("duration")
        if dur is not None:
            self.duration = float(dur)

        paused = self.mpv.get_property("pause")
        if paused is not None:
            if self.is_paused != bool(paused):
                self.is_paused = bool(paused)
                self.mpris.update_playback_status(self.is_paused)

        # Detectar fin de pista para avanzar automáticamente
        idle = self.mpv.get_property("idle-active")
        if idle and self.position > 0.0 and self.duration > 0.0:
            if self.position >= self.duration - 1.5:
                self.next_track()

    def run(self):
        self.setup_terminal()
        atexit.register(self.restore_terminal)

        def sig_handler(signum, frame):
            self.running = False
        signal.signal(signal.SIGINT, sig_handler)
        signal.signal(signal.SIGTERM, sig_handler)

        def win_handler(signum, frame):
            self.needs_full_redraw = True
        signal.signal(signal.SIGWINCH, win_handler)

        target_fps = 35.0
        frame_interval = 1.0 / target_fps
        last_draw = time.time()

        while self.running:
            now = time.time()
            elapsed = now - last_draw
            time_to_wait = max(0.001, frame_interval - elapsed)

            # Manejar pulsaciones de teclado no bloqueantes
            r, _, _ = select.select([sys.stdin], [], [], min(0.015, time_to_wait))
            if r:
                try:
                    ch = sys.stdin.read(1)
                except Exception:
                    ch = ""
                if not ch:
                    time.sleep(0.01)
                    continue
                if ch == "q" or ch == "\x03":
                    self.running = False
                    break
                elif ch == " ":
                    self.toggle_pause()
                    self._last_mpv_poll = 0.0
                elif ch == "n":
                    self.next_track()
                    self._last_mpv_poll = 0.0
                elif ch == "p":
                    self.prev_track()
                    self._last_mpv_poll = 0.0
                elif ch == "\033":
                    r2, _, _ = select.select([sys.stdin], [], [], 0.005)
                    if r2:
                        seq = sys.stdin.read(2)
                        if seq == "[C":  # Flecha derecha (+10s)
                            self.mpv.seek(10)
                            self._last_mpv_poll = 0.0
                        elif seq == "[D":  # Flecha izquierda (-10s)
                            self.mpv.seek(-10)
                            self._last_mpv_poll = 0.0
                        elif seq == "[A":  # Flecha arriba (+5 vol)
                            self.volume = min(100, self.volume + 5)
                            self.mpv.set_volume(self.volume)
                            self.mpris.update_volume(self.volume)
                        elif seq == "[B":  # Flecha abajo (-5 vol)
                            self.volume = max(0, self.volume - 5)
                            self.mpv.set_volume(self.volume)
                            self.mpris.update_volume(self.volume)

            now = time.time()
            dt = now - last_draw
            if dt >= frame_interval:
                # Actualizar estado de MPV y MPRIS (con interpolación y polling ligero)
                self.update_playback_state(dt)
                # Redibujar interfaz fluida a 35 FPS
                self.draw_screen(dt)
                last_draw = now
            else:
                rem = frame_interval - (time.time() - last_draw)
                if rem > 0.002:
                    time.sleep(rem * 0.5)

        self.restore_terminal()
        self.mpris.stop()
        self.mpv.stop()
        self.cava_reader.stop()


def main():
    try:
        parser = argparse.ArgumentParser(description="Tidal TUI Music Player (Serpantinum / Kitty)")
        parser.add_argument("--type", choices=["track", "album", "playlist"], default="track", help="Tipo de contenido")
        parser.add_argument("--id", type=str, default=None, help="ID de la pista, álbum o playlist")
        parser.add_argument("--start-idx", type=int, default=0, help="Índice de pista de inicio")
        args = parser.parse_args()

        app = TidalPlayerTUI(initial_type=args.type, initial_id=args.id, initial_start_idx=args.start_idx)
        app.run()
    except Exception as e:
        import traceback
        crash_log = os.path.join(SHARE_DIR, "player_crash.log")
        with open(crash_log, "a") as f:
            f.write(f"\n=== CRASH AT {time.ctime()} ===\n")
            traceback.print_exc(file=f)
        log.error("Error fatal en TidalPlayerTUI: %s", e)
        raise


if __name__ == "__main__":
    main()

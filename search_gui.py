#!/usr/bin/env python3
"""
Tidal Search Launcher (Serpantinum Aesthetic)
Floating PyQt6 + QML Quick Launcher with animated search and keyboard navigation.
"""

import sys
import os
import json
import socket
import subprocess
import threading

# Add local share to sys.path to import tidal_backend
SHARE_DIR = os.path.dirname(os.path.abspath(__file__))
if SHARE_DIR not in sys.path:
    sys.path.insert(0, SHARE_DIR)

import tidal_backend

from PyQt6.QtWidgets import QApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtProperty, pyqtSignal, QUrl, QTimer

SERP_DIR = os.path.expanduser("~/.local/share/serpantinum")
SERP_STATE = os.path.expanduser("~/.local/state/serpantinum")
PLAYER_SOCKET = "/tmp/tidal-player.sock"


def get_serpantinum_theme():
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
        "yellow": "#524153"
    }
    colors_file = os.path.join(SERP_STATE, "qs_colors.json")
    if os.path.isfile(colors_file):
        try:
            with open(colors_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                colors.update(data)
        except Exception:
            pass
    return colors


def play_sfx(rel_path):
    sound_file = os.path.join(SERP_DIR, "src/assets/sounds", rel_path)
    if os.path.isfile(sound_file):
        try:
            subprocess.Popen(
                ["pw-play", sound_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass


class TidalSearchBackend(QObject):
    resultsChanged = pyqtSignal()
    statusTextChanged = pyqtSignal()
    currentModeChanged = pyqtSignal()
    isSearchingChanged = pyqtSignal()
    themeChanged = pyqtSignal()

    isDetailViewChanged = pyqtSignal()
    detailDataChanged = pyqtSignal()
    detailTracksChanged = pyqtSignal()
    isLoadingDetailChanged = pyqtSignal()

    _searchDoneSignal = pyqtSignal(list, str)
    _userPlaylistsLoadedSignal = pyqtSignal(list)
    _detailDoneSignal = pyqtSignal(dict, list)

    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self._theme = get_serpantinum_theme()
        self._results = []
        self._user_playlists = []
        self._status_text = "Ingresa al menos 2 caracteres para buscar en Tidal..."
        self._current_mode = "tracks"  # "tracks", "albums", "playlists"
        self._is_searching = False
        self._pending_query = ""

        self._is_detail_view = False
        self._detail_data = {}
        self._detail_tracks = []
        self._all_detail_tracks = []
        self._is_loading_detail = False

        # Timer para debounce de búsqueda en API de Tidal
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(220)
        self._debounce_timer.timeout.connect(self._do_search_worker)

        self._searchDoneSignal.connect(self._on_search_completed)
        self._userPlaylistsLoadedSignal.connect(self._on_user_playlists_loaded)
        self._detailDoneSignal.connect(self._on_detail_completed)

        # Cargar playlists del usuario en segundo plano al iniciar
        threading.Thread(target=self._fetch_user_playlists_worker, daemon=True).start()

    def _fetch_user_playlists_worker(self):
        try:
            pls = tidal_backend.get_user_playlists()
        except Exception:
            pls = []
        self._userPlaylistsLoadedSignal.emit(pls)

    def _on_user_playlists_loaded(self, playlists: list):
        self._user_playlists = playlists
        if self._current_mode == "playlists" and len(self._pending_query) < 2 and not self._is_detail_view:
            self._results = list(self._user_playlists)
            self._status_text = "Tus playlists guardadas en Tidal" if self._results else "No tienes playlists guardadas en tu cuenta"
            self.resultsChanged.emit()
            self.statusTextChanged.emit()

    @pyqtProperty("QVariantMap", notify=themeChanged)
    def theme(self):
        return self._theme

    @pyqtProperty("QVariantList", notify=resultsChanged)
    def results(self):
        return self._results

    @pyqtProperty(str, notify=statusTextChanged)
    def statusText(self):
        return self._status_text

    @pyqtProperty(str, notify=currentModeChanged)
    def currentMode(self):
        return self._current_mode

    @pyqtProperty(bool, notify=isSearchingChanged)
    def isSearching(self):
        return self._is_searching

    @pyqtProperty(bool, notify=isDetailViewChanged)
    def isDetailView(self):
        return self._is_detail_view

    @pyqtProperty("QVariantMap", notify=detailDataChanged)
    def detailData(self):
        return self._detail_data

    @pyqtProperty("QVariantList", notify=detailTracksChanged)
    def detailTracks(self):
        return self._detail_tracks

    @pyqtProperty(bool, notify=isLoadingDetailChanged)
    def isLoadingDetail(self):
        return self._is_loading_detail

    @pyqtSlot(str, str)
    def search(self, query: str, mode: str):
        self._pending_query = query.strip()
        self._current_mode = mode
        self.currentModeChanged.emit()

        if len(self._pending_query) < 2:
            self._debounce_timer.stop()
            self._is_searching = False
            self.isSearchingChanged.emit()

            if mode == "playlists":
                # Mostrar automáticamente las playlists del usuario
                self._results = list(self._user_playlists)
                self._status_text = "Tus playlists guardadas en Tidal" if self._results else "Cargando tus playlists..."
            else:
                self._results = []
                if mode == "albums":
                    self._status_text = "Ingresa al menos 2 caracteres para buscar álbumes..."
                else:
                    self._status_text = "Ingresa al menos 2 caracteres para buscar canciones..."

            self.resultsChanged.emit()
            self.statusTextChanged.emit()
            return

        self._status_text = "Buscando en Tidal..."
        self._is_searching = True
        self.statusTextChanged.emit()
        self.isSearchingChanged.emit()
        self._debounce_timer.start()

    def _do_search_worker(self):
        q = self._pending_query
        mode = self._current_mode
        threading.Thread(target=self._search_thread, args=(q, mode), daemon=True).start()

    def _search_thread(self, query: str, mode: str):
        try:
            if mode == "albums":
                items = tidal_backend.search_albums(query, limit=35)
            elif mode == "playlists":
                items = tidal_backend.search_playlists(query, limit=35)
                # Incluir al principio las playlists del usuario que coincidan con la búsqueda
                q_lower = query.lower()
                matching_user = [p for p in self._user_playlists if q_lower in str(p.get("name", "")).lower()]
                seen = {p.get("id") for p in matching_user}
                items = matching_user + [p for p in items if p.get("id") not in seen]
            else:
                items = tidal_backend.search_tracks(query, limit=35)
        except Exception:
            items = []
        self._searchDoneSignal.emit(items, query)

    def _on_search_completed(self, items: list, query: str):
        if query != self._pending_query:
            return
        self._results = items
        self._is_searching = False
        if not items:
            self._status_text = f"No se encontraron resultados para '{query}'"
        else:
            self._status_text = ""
        self.resultsChanged.emit()
        self.isSearchingChanged.emit()
        self.statusTextChanged.emit()

    @pyqtSlot(str, str)
    def setMode(self, mode: str, current_query: str):
        if mode != self._current_mode:
            self._current_mode = mode
            self.currentModeChanged.emit()
            self.search(current_query, mode)

    @pyqtSlot("QVariantMap")
    def openDetail(self, item: dict):
        """Entra a la vista detallada de un álbum o playlist."""
        self._is_detail_view = True
        self._is_loading_detail = True
        self._detail_data = item
        self._detail_tracks = []
        self._all_detail_tracks = []
        self.isDetailViewChanged.emit()
        self.detailDataChanged.emit()
        self.detailTracksChanged.emit()
        self.isLoadingDetailChanged.emit()
        self.playClickSound()

        item_id = item.get("id")
        item_type = item.get("type", "album")

        def _worker():
            try:
                if item_type == "playlist":
                    tracks = tidal_backend.get_playlist_tracks(str(item_id))
                else:
                    tracks = tidal_backend.get_album_tracks(int(item_id))
            except Exception:
                tracks = []
            self._detailDoneSignal.emit(item, tracks)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_detail_completed(self, item: dict, tracks: list):
        if str(self._detail_data.get("id")) == str(item.get("id")):
            # Etiquetar cada pista con su índice original dentro de la colección
            for idx, t in enumerate(tracks):
                t["original_idx"] = idx
            self._all_detail_tracks = list(tracks)
            self._detail_tracks = list(tracks)
            self._is_loading_detail = False
            self.detailTracksChanged.emit()
            self.isLoadingDetailChanged.emit()

    @pyqtSlot(str)
    def filterDetailTracks(self, query: str):
        """Filtra en tiempo real los temas de la colección cargada."""
        q = (query or "").strip().lower()
        if not q:
            self._detail_tracks = list(self._all_detail_tracks)
        else:
            self._detail_tracks = [
                t for t in self._all_detail_tracks
                if q in str(t.get("name", "")).lower() or q in str(t.get("artist", "")).lower()
            ]
        self.detailTracksChanged.emit()

    @pyqtSlot()
    def closeDetail(self):
        """Regresa de la vista detallada al listado principal."""
        self._is_detail_view = False
        self._detail_tracks = []
        self._all_detail_tracks = []
        self._is_loading_detail = False
        self.isDetailViewChanged.emit()
        self.detailTracksChanged.emit()
        self.isLoadingDetailChanged.emit()
        self.playSwitchSound()

    @pyqtSlot(int)
    def playFromDetail(self, track_index: int):
        """Reproduce el álbum/playlist empezando por una pista específica."""
        if not self._detail_data:
            return
        item_id = self._detail_data.get("id")
        item_type = self._detail_data.get("type", "album")

        # Mapear al índice real original si la lista fue filtrada con búsqueda
        start_idx = track_index
        if 0 <= track_index < len(self._detail_tracks):
            start_idx = self._detail_tracks[track_index].get("original_idx", track_index)

        self.playClickSound()
        self._send_play_cmd(item_type, item_id, start_idx)
        self.closeWindow()

    @pyqtSlot()
    def playAllFromDetail(self):
        """Reproduce todo el álbum/playlist desde el inicio (#1)."""
        if not self._detail_data:
            return
        item_id = self._detail_data.get("id")
        item_type = self._detail_data.get("type", "album")
        self.playClickSound()
        self._send_play_cmd(item_type, item_id, 0)
        self.closeWindow()

    @pyqtSlot("QVariantMap")
    def playSelection(self, item: dict):
        item_type = item.get("type", "track")
        if item_type in ["album", "playlist"]:
            self.openDetail(item)
            return

        item_id = item.get("id")
        if not item_id:
            return
        self.playClickSound()
        self._send_play_cmd("track", item_id, 0)
        self.closeWindow()

    def _send_play_cmd(self, item_type: str, item_id: any, start_idx: int = 0):
        sent = False
        if os.path.exists(PLAYER_SOCKET):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(0.5)
                s.connect(PLAYER_SOCKET)
                payload = json.dumps({
                    "action": "play",
                    "type": item_type,
                    "id": item_id,
                    "start_idx": start_idx
                }) + "\n"
                s.sendall(payload.encode("utf-8"))
                s.close()
                sent = True
            except Exception:
                sent = False

        if not sent:
            cmd = [
                "kitty",
                "--class", "tidal-player-tui",
                "--title", "Tidal - Player",
                os.path.expanduser("~/.local/bin/tidal-player-tui"),
                "--type", str(item_type),
                "--id", str(item_id),
                "--start-idx", str(start_idx)
            ]
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

    @pyqtSlot()
    def playTypeSound(self):
        play_sfx("reusables/input/type.wav")

    @pyqtSlot()
    def playSwitchSound(self):
        play_sfx("reusables/switch/sfx.wav")

    @pyqtSlot()
    def playClickSound(self):
        play_sfx("reusables/clickbutton/click.wav")

    @pyqtSlot()
    def closeWindow(self):
        self.app.quit()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Tidal Search")
    app.setDesktopFileName("tidal-search-gui")

    backend = TidalSearchBackend(app)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)

    qml_file = os.path.join(SHARE_DIR, "Main.qml")
    engine.load(QUrl.fromLocalFile(qml_file))

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

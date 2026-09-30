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

# Add local share to sys.path to import modules
SHARE_DIR = os.path.dirname(os.path.abspath(__file__))
if SHARE_DIR not in sys.path:
    sys.path.insert(0, SHARE_DIR)

import config
import music_backend
import tidal_backend
import ytmusic_backend

from PyQt6.QtWidgets import QApplication
from PyQt6.QtQml import QQmlApplicationEngine
from PyQt6.QtCore import QObject, pyqtSlot, pyqtProperty, pyqtSignal, QUrl, QTimer

SERP_STATE = os.path.expanduser("~/.local/state/serpantinum")
PLAYER_SOCKET = "/tmp/tidal-player.sock"

_audio_player_cmd = None


def get_audio_player():
    global _audio_player_cmd
    if _audio_player_cmd is not None:
        return _audio_player_cmd
    import shutil
    for p in ["pw-play", "paplay", "aplay"]:
        if shutil.which(p):
            _audio_player_cmd = p
            return _audio_player_cmd
    _audio_player_cmd = ""
    return _audio_player_cmd


def get_sound_path(rel_path: str):
    candidates = [
        os.path.join(SHARE_DIR, "assets", "sounds", rel_path),
        os.path.join(SHARE_DIR, "sounds", rel_path),
        os.path.expanduser(f"~/.local/share/quick-tide/sounds/{rel_path}"),
        os.path.expanduser(f"~/.local/share/tidal-gui/sounds/{rel_path}"),
        os.path.expanduser(f"~/.local/share/serpantinum/src/assets/sounds/{rel_path}"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


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
    sound_file = get_sound_path(rel_path)
    if not sound_file:
        return
    player = get_audio_player()
    if player:
        try:
            subprocess.Popen(
                [player, sound_file],
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

    isSetupWizardChanged = pyqtSignal()
    activeServiceChanged = pyqtSignal()
    tidalLoggedInChanged = pyqtSignal()
    tidalAuthUrlChanged = pyqtSignal()
    tidalUserCodeChanged = pyqtSignal()
    isLoggingInTidalChanged = pyqtSignal()
    tidalLoginStatusChanged = pyqtSignal()

    youtubeLoggedInChanged = pyqtSignal()
    isSyncingYoutubeChanged = pyqtSignal()
    youtubeLoginStatusChanged = pyqtSignal()

    _searchDoneSignal = pyqtSignal(list, str, str)
    _userPlaylistsLoadedSignal = pyqtSignal(list)
    _detailDoneSignal = pyqtSignal(dict, list)
    _tidalLoginSuccessSignal = pyqtSignal(str)
    _tidalLoginErrorSignal = pyqtSignal(str)
    _youtubeSyncDoneSignal = pyqtSignal(bool, str)

    def __init__(self, app_instance):
        super().__init__()
        self.app = app_instance
        self._theme = get_serpantinum_theme()
        self._results = []
        self._user_playlists = []
        self._active_service = config.get_active_service()
        self._is_setup_wizard = not config.is_setup_completed()
        self._tidal_logged_in = tidal_backend.is_logged_in()
        self._tidal_auth_url = ""
        self._tidal_user_code = ""
        self._is_logging_in_tidal = False
        self._tidal_login_status = ""

        self._youtube_logged_in = ytmusic_backend.is_logged_in()
        self._is_syncing_youtube = False
        self._youtube_login_status = "Playlists sincronizadas" if self._youtube_logged_in else "Sin sincronizar"

        if self._active_service == "youtube":
            self._status_text = "Ingresa al menos 2 caracteres para buscar en YouTube Music..."
        else:
            self._status_text = "Ingresa al menos 2 caracteres para buscar en Tidal..."

        self._current_mode = "tracks"  # "tracks", "albums", "playlists"
        self._is_searching = False
        self._pending_query = ""

        self._is_detail_view = False
        self._detail_data = {}
        self._detail_tracks = []
        self._all_detail_tracks = []
        self._is_loading_detail = False

        # Timer para debounce de búsqueda
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(220)
        self._debounce_timer.timeout.connect(self._do_search_worker)

        self._searchDoneSignal.connect(self._on_search_completed)
        self._userPlaylistsLoadedSignal.connect(self._on_user_playlists_loaded)
        self._detailDoneSignal.connect(self._on_detail_completed)
        self._tidalLoginSuccessSignal.connect(self._on_tidal_login_success)
        self._tidalLoginErrorSignal.connect(self._on_tidal_login_error)
        self._youtubeSyncDoneSignal.connect(self._on_youtube_sync_done)

        # Cargar playlists de usuario en segundo plano según el servicio activo
        threading.Thread(target=self._fetch_user_playlists_worker, daemon=True).start()

        # Warmup de yt-dlp en segundo plano para que la primera búsqueda sea instantánea
        def _warmup():
            try:
                ytmusic_backend.get_ytdl()
            except Exception:
                pass
        threading.Thread(target=_warmup, daemon=True).start()

    def _fetch_user_playlists_worker(self):
        try:
            pls = music_backend.get_user_playlists()
        except Exception:
            pls = []
        self._userPlaylistsLoadedSignal.emit(pls)

    def _on_user_playlists_loaded(self, playlists: list):
        self._user_playlists = playlists
        if self._current_mode == "playlists" and len(self._pending_query) < 2 and not self._is_detail_view:
            self._results = list(self._user_playlists)
            svc_name = "YouTube Music" if self._active_service == "youtube" else "Tidal"
            self._status_text = f"Tus playlists guardadas en {svc_name}" if self._results else f"No tienes playlists guardadas en {svc_name}"
            self.resultsChanged.emit()
            self.statusTextChanged.emit()

    @pyqtProperty(bool, notify=isSetupWizardChanged)
    def isSetupWizard(self):
        return self._is_setup_wizard

    @pyqtProperty(str, notify=activeServiceChanged)
    def activeService(self):
        return self._active_service

    @pyqtProperty(bool, notify=tidalLoggedInChanged)
    def tidalLoggedIn(self):
        return self._tidal_logged_in

    @pyqtProperty(str, notify=tidalAuthUrlChanged)
    def tidalAuthUrl(self):
        return self._tidal_auth_url

    @pyqtProperty(str, notify=tidalUserCodeChanged)
    def tidalUserCode(self):
        return self._tidal_user_code

    @pyqtProperty(bool, notify=isLoggingInTidalChanged)
    def isLoggingInTidal(self):
        return self._is_logging_in_tidal

    @pyqtProperty(str, notify=tidalLoginStatusChanged)
    def tidalLoginStatus(self):
        return self._tidal_login_status

    @pyqtProperty(bool, notify=youtubeLoggedInChanged)
    def youtubeLoggedIn(self):
        return self._youtube_logged_in

    @pyqtProperty(bool, notify=isSyncingYoutubeChanged)
    def isSyncingYoutube(self):
        return self._is_syncing_youtube

    @pyqtProperty(str, notify=youtubeLoginStatusChanged)
    def youtubeLoginStatus(self):
        return self._youtube_login_status

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

    @pyqtSlot(str)
    def selectService(self, service: str):
        config.set_active_service(service)
        self._active_service = service
        self._is_setup_wizard = False
        self.activeServiceChanged.emit()
        self.isSetupWizardChanged.emit()
        self.playClickSound()

        svc_name = "YouTube Music" if service == "youtube" else "Tidal"
        self._status_text = f"Servicio activo: {svc_name}. Ingresa texto para buscar..."
        self.statusTextChanged.emit()

        # Cargar playlists de usuario para el servicio seleccionado
        threading.Thread(target=self._fetch_user_playlists_worker, daemon=True).start()

        if len(self._pending_query) >= 2:
            self._debounce_timer.start()

    @pyqtSlot()
    def startTidalLogin(self):
        self.playClickSound()
        self._is_logging_in_tidal = True
        self._tidal_login_status = "Iniciando autorización con Tidal..."
        self.isLoggingInTidalChanged.emit()
        self.tidalLoginStatusChanged.emit()

        def _on_success(user_name):
            try:
                self._tidalLoginSuccessSignal.emit(user_name)
            except RuntimeError:
                pass

        def _on_error(err):
            try:
                self._tidalLoginErrorSignal.emit(err)
            except RuntimeError:
                pass

        def _starter():
            try:
                auth_url, user_code = tidal_backend.start_oauth_login(on_success=_on_success, on_error=_on_error)
                if not auth_url.startswith("http"):
                    auth_url = "https://" + auth_url
                self._tidal_auth_url = auth_url
                self._tidal_user_code = user_code
                self._tidal_login_status = f"Por favor autoriza el código {user_code} en tu navegador..."
                self.tidalAuthUrlChanged.emit()
                self.tidalUserCodeChanged.emit()
                self.tidalLoginStatusChanged.emit()

                # Abrir navegador automáticamente
                import webbrowser
                webbrowser.open(auth_url)
            except Exception as e:
                self._tidalLoginErrorSignal.emit(str(e))

        threading.Thread(target=_starter, daemon=True).start()

    def _on_tidal_login_success(self, user_name: str):
        self._tidal_logged_in = True
        self._is_logging_in_tidal = False
        self._tidal_login_status = f"¡Sesión iniciada con éxito como {user_name}!"
        self.tidalLoggedInChanged.emit()
        self.isLoggingInTidalChanged.emit()
        self.tidalLoginStatusChanged.emit()
        self.playClickSound()
        self.selectService("tidal")

    def _on_tidal_login_error(self, err: str):
        self._is_logging_in_tidal = False
        self._tidal_login_status = f"Error al iniciar sesión: {err}"
        self.isLoggingInTidalChanged.emit()
        self.tidalLoginStatusChanged.emit()

    @pyqtSlot()
    def syncYoutubeAccount(self):
        self.playClickSound()
        self._is_syncing_youtube = True
        self._youtube_login_status = "Detectando navegadores y sincronizando playlists..."
        self.isSyncingYoutubeChanged.emit()
        self.youtubeLoginStatusChanged.emit()

        def _worker():
            ok, msg = ytmusic_backend.sync_browser_cookies()
            self._youtubeSyncDoneSignal.emit(ok, msg)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_youtube_sync_done(self, ok: bool, msg: str):
        self._is_syncing_youtube = False
        self._youtube_logged_in = ok
        self._youtube_login_status = msg
        self.isSyncingYoutubeChanged.emit()
        self.youtubeLoggedInChanged.emit()
        self.youtubeLoginStatusChanged.emit()
        if ok:
            self.playClickSound()
            threading.Thread(target=self._fetch_user_playlists_worker, daemon=True).start()

    @pyqtSlot()
    def openSettings(self):
        self._is_setup_wizard = True
        self.isSetupWizardChanged.emit()
        self.playClickSound()

    @pyqtSlot()
    def closeSettings(self):
        self._is_setup_wizard = False
        self.isSetupWizardChanged.emit()
        self.playSwitchSound()

    @pyqtSlot(str)
    def openBrowser(self, url: str):
        import webbrowser
        webbrowser.open(url)

    @pyqtSlot(str, str)
    def search(self, query: str, mode: str):
        self._pending_query = query.strip()
        self._current_mode = mode
        self.currentModeChanged.emit()

        svc_name = "YouTube Music" if self._active_service == "youtube" else "Tidal"

        if len(self._pending_query) < 2:
            self._debounce_timer.stop()
            self._is_searching = False
            self.isSearchingChanged.emit()

            if mode == "playlists":
                self._results = list(self._user_playlists)
                self._status_text = f"Tus playlists guardadas en {svc_name}" if self._results else f"No tienes playlists guardadas en {svc_name}"
            else:
                self._results = []
                if mode == "albums":
                    self._status_text = f"Ingresa al menos 2 caracteres para buscar álbumes en {svc_name}..."
                else:
                    self._status_text = f"Ingresa al menos 2 caracteres para buscar canciones en {svc_name}..."

            self.resultsChanged.emit()
            self.statusTextChanged.emit()
            return

        self._status_text = f"Buscando en {svc_name}..."
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
                items = music_backend.search_albums(query, limit=35)
            elif mode == "playlists":
                items = music_backend.search_playlists(query, limit=35)
                if self._user_playlists:
                    q_lower = query.lower()
                    matching_user = [p for p in self._user_playlists if q_lower in str(p.get("name", "")).lower()]
                    seen = {p.get("id") for p in matching_user}
                    items = matching_user + [p for p in items if p.get("id") not in seen]
            else:
                items = music_backend.search_tracks(query, limit=35)
        except Exception:
            items = []
        self._searchDoneSignal.emit(items, query, mode)

    def _on_search_completed(self, items: list, query: str, mode: str):
        if query != self._pending_query or mode != self._current_mode:
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
        provider = item.get("provider", self._active_service)

        def _worker():
            try:
                if item_type == "playlist":
                    tracks = music_backend.get_playlist_tracks(str(item_id), provider)
                else:
                    tracks = music_backend.get_album_tracks(item_id, provider)
            except Exception:
                tracks = []
            self._detailDoneSignal.emit(item, tracks)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_detail_completed(self, item: dict, tracks: list):
        if str(self._detail_data.get("id")) == str(item.get("id")):
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
        provider = self._detail_data.get("provider", self._active_service)

        # Mapear al índice real original si la lista fue filtrada con búsqueda
        start_idx = track_index
        if 0 <= track_index < len(self._detail_tracks):
            start_idx = self._detail_tracks[track_index].get("original_idx", track_index)

        self.playClickSound()
        self._send_play_cmd(item_type, item_id, start_idx, provider)
        self.closeWindow()

    @pyqtSlot()
    def playAllFromDetail(self):
        """Reproduce todo el álbum/playlist desde el inicio (#1)."""
        if not self._detail_data:
            return
        item_id = self._detail_data.get("id")
        item_type = self._detail_data.get("type", "album")
        provider = self._detail_data.get("provider", self._active_service)
        self.playClickSound()
        self._send_play_cmd(item_type, item_id, 0, provider)
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
        provider = item.get("provider", self._active_service)
        self.playClickSound()
        self._send_play_cmd("track", item_id, 0, provider)
        self.closeWindow()

    def _send_play_cmd(self, item_type: str, item_id: any, start_idx: int = 0, provider: str = "tidal"):
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
                    "start_idx": start_idx,
                    "provider": provider,
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
                "--title", "Quick-Tide - Player",
                os.path.expanduser("~/.local/bin/tidal-player-tui"),
                "--type", str(item_type),
                "--id", str(item_id),
                "--start-idx", str(start_idx),
                "--provider", str(provider),
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

version = 1.3.0

# Registro de Cambios (Changelog) - Quick-Tide

## [1.3.0] - 2026-09-28
### Añadido
- **Arquitectura Multi-Servicio Universal**: soporte integrado para **YouTube Music** (sin necesidad de cuenta, streaming Opus Hi-Fi) y **Tidal Hi-Fi** (autenticación nativa OAuth sin depender de programas externos).
- **Asistente de Configuración Inicial (Setup Wizard)**: interfaz interactiva con estética Serpantinum / Liquid Glass en la primera apertura para seleccionar tu servicio o reconfigurar con `Ctrl + ,` / botón `⚙`.
- **Sincronización de Playlists de YouTube con un clic**: importación automática de playlists personales y música que te gusta desde Zen Browser o Chromium sin escribir contraseñas.
- **Arranque Instantáneo (16x más veloz)**: inicialización asíncrona de motores pesados (`yt_dlp` y `tidalapi`) reduciendo el tiempo de apertura de ~1.5s a menos de ~100ms.
- **Carátulas de Estudio 1400x1400**: integración con las APIs públicas de Apple Music (iTunes) y Deezer para descargar carátulas cuadradas de ultra alta resolución para YouTube Music, evitando miniaturas 16:9 con barras negras en Kitty.
- **Navegación 100% por Teclado**: control con `Tab` que cicla armónicamente entre pestañas y el selector de servicio, y navegación por flechas (`←` / `→`), `Enter` y `S` dentro del asistente.
- **Diseño de Header Limpio**: reubicación de los atajos al footer inferior para evitar solapamientos con títulos largos de canciones.

## [1.2.0] - 2026-09-28
### Añadido
- **Instalador Universal y Detección Automática**: compatible de forma nativa con Hyprland, KDE Plasma, GNOME, Sway, Niri y XFCE.
- **Assets de Sonido Integrados**: efectos sonoros táctiles autónomos empaquetados directamente en el repositorio (`assets/sounds/`), sin requerir dependencias externas de shell.
- **Integración Nativa de Last.fm**: scrobbling en tiempo real (Now Playing + Scrobble tras el 50% o 4 min) con comandos interactivos `--setup-lastfm` y `--test-lastfm`.
- **Corrección SOTA de MPRIS2**: sincronización exacta de la posición en la barra/shell (`Seeked` signal, reset instantáneo en `new_track` y control bidireccional de volumen).
- **Optimización de Rendimiento**: motor MPV con identificadores atómicos `request_id`, búfer persistente, precomputación de decaimiento en visualizador CAVA y reducción del 75% en tráfico IPC durante crossfade.
- **Acceso Directo `.desktop`**: integración con los menús de aplicaciones del sistema (`quick-tide.desktop` y `quick-tide-player.desktop`).
- **Actualizador Inteligente (`update.sh`)**: verificación de versiones semánticas contra GitHub y actualización limpia con un solo comando.

## [1.1.0] - 2026-09-08
### Añadido
- **True Dual-Deck Crossfade**: mezcla simultánea entre dos instancias de MPV con curvas acústicas Equal-Power.
- **Configuración centralizada**: soporte para `~/.config/quick-tide/config.toml` con opciones de calidad y duración de crossfade.
- **Mejoras visuales**: carátula ampliada, visualizador CAVA adaptativo y letras 3D cilíndricas con LRCLIB.

## [1.0.0] - 2026-09-08
### Versión inicial
- Lanzador flotante `Super + T` en PyQt6 y QML con estética Serpantinum.
- Reproductor TUI en Kitty terminal con carátulas mediante `kitten icat`.
- Integración con OAuth y sesiones de Tidal a través de `low-tide`.

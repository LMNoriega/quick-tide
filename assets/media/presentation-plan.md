# Brag Plan: Quick-Tide (Tidal Hi-Fi Suite)

## What is this app?
Un reproductor TUI y lanzador flotante ultrarrápido para Tidal en Arch Linux / Hyprland, con visualizador de audio en tiempo real con CAVA/PipeWire, letras sincronizadas con LRCLIB, carátulas en Kitty, crossfade simultáneo de doble deck con curvas Equal-Power, streaming FLAC sin pérdidas y scrobbling nativo con Last.fm.

## The angle
Tidal con calidad audiófila Hi-Res FLAC integrado nativamente en tu entorno Arch Linux / Hyprland: adiós a las aplicaciones web pesadas de Electron. Una interfaz dividida en dos módulos armónicos (reproductor + letras 3D) con estética Serpantinum, visualizador CAVA físico a 35 FPS y scrobbling en tiempo real a Last.fm.

## Hook (first 2-3 seconds)
El atajo `SUPER + T` despliega al instante el lanzador flotante con bordes malva resplandecientes sobre fondo translúcido Serpantinum (`#110d11`), filtrando temas, álbumes y playlists con badges de calidad (`FLAC`, `HI-RES`, `MAX`).

## Key moments (the middle)
- **Apertura de la TUI en Kitty con Carátula & CAVA**: Transición a la terminal flotante con la carátula en alta definición y las barras físicas de CAVA danzando con espectro real de PipeWire.
- **Letras sincronizadas en cilindro 3D**: Desplazamiento reactivo de letras con degradado de foco (línea activa brillante con `▶` y líneas periféricas atenuadas).
- **Dual-Deck Crossfade & Last.fm**: Transición suave entre pistas con curva Equal-Power (`⇄ MEZCLANDO`) y confirmación del scrobble (`󰓇 Scrobbled ✓`).

## Outro / punchline
"Quick-Tide: La experiencia definitiva de Tidal para usuarios de Arch Linux y Hyprland."

## User flow worth showing
1. **Búsqueda instantánea**: Atajo `SUPER + T` abre el menú contextual y busca música en Tidal con resultados en tiempo real.
2. **Reproducción audiófila**: Abre la TUI en Kitty con CAVA en tiempo real, carátula nativa y letras sincronizadas con LRCLIB.
3. **Control y sincronización**: Salto con flechas, crossfade simultáneo de doble deck y sincronización automática con Last.fm.

## Tone
- Preset: `polished`
- Creative direction: Futuristic dark-mode Linux terminal Hi-Fi audiophile launch
- Interpretation: Transiciones nítidas, tipografía JetBrains Mono clara, acentos Serpantinum (malva, durazno, cyan FLAC) y ritmo visual dinámico.

## Format: landscape — 1920x1080
## Duration: 18 seconds

## Visual identity (from the project)
- Background: `#110d11` (base Serpantinum con acento frosted glass)
- Surface: `#1f1a1f`, `#231e23`
- Accent Primary (Mauve): `#e9b5ef`
- Accent Secondary (Peach): `#f5b7b0`
- Accent Audio (Cyan FLAC): `#00d2ff`
- Accent Audio (Hi-Res Gold): `#f5c542`
- Accent Last.fm (Red): `#ffb4ab`
- Text Primary: `#eae0e7`
- Text Subtext: `#cfc3cd` / `#988d97`
- Font: `JetBrains Mono, Inter, system-ui, sans-serif`
- Strongest visual element: La terminal TUI con carátula cuadrada, barras ecualizadoras de CAVA y letras 3D.

## Share copy (draft)
Quick-Tide: un reproductor TUI y lanzador flotante para Tidal en Arch Linux con audio Hi-Fi FLAC, visualizador CAVA, letras sincronizadas, crossfade y Last.fm. 🎧✨

## Audio direction
- Role: Warm electronic tech bed con efectos táctiles de la suite.
- Music: `happy-beats-business-moves-vol-12-by-ende-dot-app.mp3`
- Music treatment: Cama musical a volumen 0.35 con fade-out en los últimos 1.5s.
- Music cue guidance: Tempo ~110 BPM. Cues mayores en 4.39s (apertura TUI), 8.74s (cambio a CAVA/letras), 13.11s (crossfade/lastfm) y 17.47s (outro).
- Audio-reactive treatment: Sutil respiración del resplandor de fondo y borde de la ventana según la energía musical.
- SFX posture: Moderada y táctil (sonidos de interfaz `type.wav`, `sfx.wav`, `click.wav`, `Progress.wav`).

## Storyboard

### Scene 1 — Invocación Spotlight (Super + T) — 4.0s
Aparece el atajo `SUPER + T` iluminándose en el centro sobre fondo oscuro Serpantinum. Se despliega la ventana flotante `tidal-search-gui` con efecto de vidrio esmerilado. Se tipea "Daft Punk" y emergen resultados instantáneos con badges de calidad `FLAC • 1411 kbps` y `HI-RES`.

### Scene 2 — Reproductor TUI & Visualizador CAVA — 5.0s
Enter activa la reproducción. La ventana se transforma en la terminal flotante de Kitty `tidal-player-tui`. A la izquierda: carátula del álbum en alta resolución y las 24 barras de CAVA oscilando con física realista en tonos malva y durazno. Fila de metadatos con el badge cyan `FLAC` y duración en tiempo real.

### Scene 3 — Letras Sincronizadas & Dual-Deck Crossfade — 5.0s
A la derecha se ilumina la columna de letras sincronizadas con efecto de cilindro 3D (la línea activa resalta en malva neón con `▶`). Se activa la tecla `x`: la barra de estado conmuta a `⇄ MEZCLANDO` mostrando el fundido suave entre temas. En la esquina izquierda se ilumina el distintivo `󰓇 Last.fm: Scrobbled ✓`.

### Scene 4 — Outro & Hi-Fi Arch Linux Suite — 4.0s
Transición a la tarjeta central con el logo 🎧 y tipografía nítida: "Quick-Tide". Se despliegan los distintivos de calidad: "Arch Linux · Hyprland · Kitty TUI · Hi-Res FLAC · CAVA Spectrum · Last.fm".

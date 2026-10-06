#!/usr/bin/env bash
# ==============================================================================
# Quick-Tide (Tidal Hi-Fi Suite) - Script de Instalación Universal
# Compatible con: Hyprland, KDE Plasma, GNOME, Sway, Niri, XFCE y más
# ==============================================================================

set -e

BOLD="\033[1m"
GREEN="\033[1;32m"
BLUE="\033[1;34m"
CYAN="\033[1;36m"
YELLOW="\033[1;33m"
PURPLE="\033[1;35m"
RED="\033[1;31m"
RESET="\033[0m"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ACTION="auto"
for arg in "$@"; do
    case "$arg" in
        --update|-u)
            ACTION="update"
            ;;
        --reinstall|--full)
            ACTION="full"
            ;;
        --help|-h)
            echo "Uso: ./install.sh [OPCIONES]"
            echo ""
            echo "Opciones:"
            echo "  --update, -u         Actualizar a la última versión (rápido, conserva atajos y config)"
            echo "  --reinstall, --full  Reinstalación y reconfiguración completa desde cero"
            echo "  --help, -h           Mostrar esta ayuda"
            exit 0
            ;;
    esac
done

# Detección de instalación previa si no se especificó un flag explícito
if [ "$ACTION" = "auto" ] && ([ -f "$HOME/.local/bin/tidal-search-gui" ] || [ -f "$HOME/.local/bin/quick-tide" ]); then
    echo -e "${PURPLE}╭──────────────────────────────────────────────────────────╮${RESET}"
    echo -e "${PURPLE}│${RESET}             ${BOLD}QUICK-TIDE (TIDAL HI-FI SUITE)${RESET}               ${PURPLE}│${RESET}"
    echo -e "${PURPLE}╰──────────────────────────────────────────────────────────╯${RESET}"
    echo ""
    echo -e "${CYAN}==> Se detectó una instalación previa de Quick-Tide en ~/.local/bin/${RESET}"
    echo ""
    echo -e "  ${BOLD}1)${RESET} ${GREEN}${BOLD}Actualizar a la última versión${RESET} (rápido: actualiza código, binarios y assets, conservando atajos y config)"
    echo -e "  ${BOLD}2)${RESET} ${YELLOW}Reinstalar / Reconfigurar desde cero${RESET} (vuelve a comprobar dependencias y reconfigurar atajos)"
    echo -e "  ${BOLD}3)${RESET} Salir"
    echo ""
    read -rp "  Selecciona una opción [1/2/3, por defecto: 1]: " opc
    opc=${opc:-1}
    case "$opc" in
        1)
            ACTION="update"
            ;;
        2)
            ACTION="full"
            ;;
        *)
            echo "Operación cancelada."
            exit 0
            ;;
    esac
fi

get_file_version() {
    local f="$1"
    if [ -f "$f" ]; then
        head -n 5 "$f" | grep -iE '^(version|VERSION)[[:space:]]*=' | head -n 1 | sed -E 's/^[vV][eE][rR][sS][iI][oO][nN][[:space:]]*=[[:space:]]*["'"'"']?([^"'"'"' ]+)["'"'"']?.*/\1/'
    fi
}

# ------------------------------------------------------------------------------
# MODO ACTUALIZACIÓN RÁPIDA
# ------------------------------------------------------------------------------
if [ "$ACTION" = "update" ]; then
    echo -e "${PURPLE}╭──────────────────────────────────────────────────────────╮${RESET}"
    echo -e "${PURPLE}│${RESET}             ${BOLD}ACTUALIZADOR DE QUICK-TIDE${RESET}                   ${PURPLE}│${RESET}"
    echo -e "${PURPLE}╰──────────────────────────────────────────────────────────╯${RESET}"
    echo ""
    echo -e "${BLUE}==> Comprobando versiones y actualizaciones...${RESET}"

    # 1. Obtener versión local
    LOCAL_VER=$(get_file_version "$HOME/.local/share/quick-tide/CHANGELOG.md")
    if [ -z "$LOCAL_VER" ]; then
        LOCAL_VER=$(get_file_version "$HOME/.local/share/tidal-gui/CHANGELOG.md")
    fi
    if [ -z "$LOCAL_VER" ]; then
        LOCAL_VER=$(get_file_version "$DIR/CHANGELOG.md")
    fi
    LOCAL_VER="${LOCAL_VER:-1.0.0}"

    # 2. Obtener versión remota desde GitHub
    REMOTE_VER=""
    REMOTE_URL=$(git -C "$DIR" remote get-url origin 2>/dev/null || echo "https://github.com/LMNoriega/quick-tide.git")
    REPO_PATH=$(echo "$REMOTE_URL" | sed -E 's#(.*github\.com[/:]|\.git$)##g')
    RAW_URL="https://raw.githubusercontent.com/${REPO_PATH}/main/CHANGELOG.md"

    if command -v curl >/dev/null 2>&1; then
        REMOTE_CONTENT=$(curl -sSL --connect-timeout 4 "$RAW_URL" 2>/dev/null || true)
    elif command -v wget >/dev/null 2>&1; then
        REMOTE_CONTENT=$(wget -qO- --timeout=4 "$RAW_URL" 2>/dev/null || true)
    fi

    if [ -n "$REMOTE_CONTENT" ]; then
        REMOTE_VER=$(echo "$REMOTE_CONTENT" | head -n 5 | grep -iE '^(version|VERSION)[[:space:]]*=' | head -n 1 | sed -E 's/^[vV][eE][rR][sS][iI][oO][nN][[:space:]]*=[[:space:]]*["'"'"']?([^"'"'"' ]+)["'"'"']?.*/\1/')
    fi

    if [ -z "$REMOTE_VER" ] && [ -d "$DIR/.git" ] && command -v git >/dev/null 2>&1; then
        git -C "$DIR" fetch origin main 2>/dev/null || true
        REMOTE_CHANGELOG=$(git -C "$DIR" show origin/main:CHANGELOG.md 2>/dev/null || true)
        if [ -n "$REMOTE_CHANGELOG" ]; then
            REMOTE_VER=$(echo "$REMOTE_CHANGELOG" | head -n 5 | grep -iE '^(version|VERSION)[[:space:]]*=' | head -n 1 | sed -E 's/^[vV][eE][rR][sS][iI][oO][nN][[:space:]]*=[[:space:]]*["'"'"']?([^"'"'"' ]+)["'"'"']?.*/\1/')
        fi
    fi

    echo -e "  Versión instalada: ${CYAN}v${LOCAL_VER}${RESET}"

    if [ -n "$REMOTE_VER" ]; then
        echo -e "  Versión en GitHub: ${CYAN}v${REMOTE_VER}${RESET}"
        if [ "$LOCAL_VER" = "$REMOTE_VER" ]; then
            echo -e "\n  ${GREEN}✔ ¡Ya tienes la última versión instalada (v${LOCAL_VER})!${RESET}"
            echo -e "  No hay nuevas actualizaciones disponibles."
            read -rp "  ¿Deseas forzar la reinstalación de todos modos? [s/N]: " force_inst
            force_inst=${force_inst:-N}
            if [[ ! "$force_inst" =~ ^[sS]$ ]]; then
                echo -e "  Operación finalizada."
                exit 0
            fi
        elif [ "$(printf '%s\n%s\n' "$LOCAL_VER" "$REMOTE_VER" | sort -V | head -n1)" = "$LOCAL_VER" ]; then
            echo -e "\n  ${GREEN}${BOLD}🚀 ¡Nueva versión disponible: v${REMOTE_VER}!${RESET} (Tu versión: v${LOCAL_VER})"
        else
            echo -e "\n  ${YELLOW}Tu versión actual (v${LOCAL_VER}) es más reciente o de desarrollo respecto a GitHub (v${REMOTE_VER}).${RESET}"
        fi
    else
        echo -e "  ${YELLOW}! No se pudo comprobar la versión remota en GitHub (sin conexión). Procediendo con actualización local.${RESET}"
    fi

    echo -e "\n${BLUE}==> Aplicando actualización...${RESET}"

    # 3. Sincronización con Git si aplica
    if [ -d "$DIR/.git" ] && command -v git >/dev/null 2>&1; then
        echo -e "  ${BLUE}• Descargando últimos cambios de GitHub...${RESET}"
        if [ -n "$(git -C "$DIR" status --porcelain 2>/dev/null)" ]; then
            echo -e "  ${YELLOW}! Aviso: Se detectaron cambios locales modificados en el repositorio.${RESET}"
            read -rp "  ¿Deseas descartar cambios locales y actualizar con la versión oficial limpia de GitHub? [S/n]: " reset_git
            reset_git=${reset_git:-S}
            if [[ "$reset_git" =~ ^[sS]$ ]]; then
                git -C "$DIR" fetch origin 2>/dev/null || true
                git -C "$DIR" reset --hard origin/main 2>/dev/null || true
                echo -e "  ${GREEN}✔ Repositorio sincronizado con la versión oficial limpia de GitHub.${RESET}"
            else
                echo -e "  ${YELLOW}Conservando cambios locales del repositorio.${RESET}"
            fi
        else
            git -C "$DIR" pull --rebase origin main 2>/dev/null || git -C "$DIR" pull origin main 2>/dev/null || true
            echo -e "  ${GREEN}✔ Repositorio actualizado con la última versión de GitHub.${RESET}"
        fi
    fi

    # 4. Actualizar archivos locales
    echo -e "  ${BLUE}• Actualizando binarios y recursos locales...${RESET}"
    TARGET_SHARE="$HOME/.local/share/quick-tide"
    mkdir -p "$HOME/.local/bin"
    mkdir -p "$TARGET_SHARE/bin"
    mkdir -p "$TARGET_SHARE/sounds"
    mkdir -p "$HOME/.local/share/applications"

    # Instalar scripts base en share
    cp -f "$DIR/Main.qml" "$TARGET_SHARE/Main.qml"
    cp -f "$DIR/player_tui.py" "$TARGET_SHARE/player_tui.py"
    cp -f "$DIR/search_gui.py" "$TARGET_SHARE/search_gui.py"
    cp -f "$DIR/scrobbler.py" "$TARGET_SHARE/scrobbler.py"
    cp -f "$DIR/tidal_backend.py" "$TARGET_SHARE/tidal_backend.py"
    cp -f "$DIR/tidal_client.py" "$TARGET_SHARE/tidal_client.py"
    cp -f "$DIR/ytmusic_backend.py" "$TARGET_SHARE/ytmusic_backend.py"
    cp -f "$DIR/music_backend.py" "$TARGET_SHARE/music_backend.py"
    cp -f "$DIR/lyrics.py" "$TARGET_SHARE/lyrics.py"
    cp -f "$DIR/config.py" "$TARGET_SHARE/config.py"
    if [ -f "$DIR/CHANGELOG.md" ]; then
        cp -f "$DIR/CHANGELOG.md" "$TARGET_SHARE/CHANGELOG.md"
    fi

    # Copiar ejecutables y wrappers
    cp -rf "$DIR/bin/"* "$TARGET_SHARE/bin/"
    chmod +x "$TARGET_SHARE/bin/"*

    # Copiar sonidos integrados
    if [ -d "$DIR/assets/sounds" ]; then
        cp -rf "$DIR/assets/sounds/"* "$TARGET_SHARE/sounds/"
    fi

    # Copiar iconos y assets
    if [ -d "$DIR/assets/icons" ]; then
        mkdir -p "$TARGET_SHARE/assets/icons"
        cp -rf "$DIR/assets/icons/"* "$TARGET_SHARE/assets/icons/"
    fi

    # Instalar ejecutables en ~/.local/bin
    chmod +x "$DIR/bin/"*
    ln -sf "$TARGET_SHARE/bin/tidal-search-gui" "$HOME/.local/bin/tidal-search-gui" 2>/dev/null || ln -sf "$DIR/bin/tidal-search-gui" "$HOME/.local/bin/tidal-search-gui"
    ln -sf "$TARGET_SHARE/bin/tidal-player-tui" "$HOME/.local/bin/tidal-player-tui" 2>/dev/null || ln -sf "$DIR/bin/tidal-player-tui" "$HOME/.local/bin/tidal-player-tui"
    ln -sf "$HOME/.local/bin/tidal-search-gui" "$HOME/.local/bin/quick-tide"
    ln -sf "$HOME/.local/bin/tidal-player-tui" "$HOME/.local/bin/quick-tide-player"
    ln -sf "$DIR/update.sh" "$HOME/.local/bin/quick-tide-update"

    # Mantener enlace legacy si existía
    if [ ! -e "$HOME/.local/share/tidal-gui" ]; then
        ln -sf "$TARGET_SHARE" "$HOME/.local/share/tidal-gui" 2>/dev/null || true
    fi

    # Actualizar accesos directos de escritorio
    if [ -d "$DIR/desktop" ]; then
        cp -f "$DIR/desktop/"*.desktop "$HOME/.local/share/applications/" 2>/dev/null || true
        if command -v update-desktop-database >/dev/null 2>&1; then
            update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
        fi
    fi

    UPDATED_VER=$(get_file_version "$TARGET_SHARE/CHANGELOG.md")
    UPDATED_VER="${UPDATED_VER:-$REMOTE_VER}"
    echo -e "\n${GREEN}${BOLD}✔ ¡Quick-Tide ha sido actualizado con éxito a la versión v${UPDATED_VER:-1.2.0}!${RESET}"
    echo -e "  Tus configuraciones en ~/.config/quick-tide/config.toml y atajos se han conservado intactos."
    echo ""
    exit 0
fi

# ------------------------------------------------------------------------------
# MODO INSTALACIÓN COMPLETA
# ------------------------------------------------------------------------------
echo -e "${PURPLE}╭──────────────────────────────────────────────────────────╮${RESET}"
echo -e "${PURPLE}│${RESET}             ${BOLD}INSTALADOR DE QUICK-TIDE${RESET}                     ${PURPLE}│${RESET}"
echo -e "${PURPLE}│${RESET}      Tidal Hi-Fi Suite para Linux (TUI + QML Launcher)   ${PURPLE}│${RESET}"
echo -e "${PURPLE}╰──────────────────────────────────────────────────────────╯${RESET}"
echo ""

# 1. Comprobación y sugerencia de dependencias
echo -e "${BLUE}==> 1. Comprobando dependencias del sistema...${RESET}"

MISSING_PKGS=()

# Comprobar Python3
if ! command -v python3 >/dev/null 2>&1; then
    MISSING_PKGS+=("python")
fi

# Comprobar PyQt6
if ! python3 -c "import PyQt6" >/dev/null 2>&1; then
    MISSING_PKGS+=("python-pyqt6")
fi

# Comprobar MPV
if ! command -v mpv >/dev/null 2>&1; then
    MISSING_PKGS+=("mpv")
fi

# Comprobar CAVA
if ! command -v cava >/dev/null 2>&1; then
    MISSING_PKGS+=("cava")
fi

# Comprobar yt-dlp (YouTube Music)
if ! command -v yt-dlp >/dev/null 2>&1; then
    MISSING_PKGS+=("yt-dlp")
fi

# Comprobar python-dbus-next (Integración MPRIS2 multimedia en escritorio)
if ! python3 -c "import dbus_next" >/dev/null 2>&1; then
    MISSING_PKGS+=("python-dbus-next")
fi

# Comprobar python-pillow (recorte de carátulas de YouTube)
if ! python3 -c "import PIL" >/dev/null 2>&1; then
    MISSING_PKGS+=("python-pillow")
fi

# Comprobar python-tidalapi (Streaming nativo de Tidal)
if ! python3 -c "import tidalapi" >/dev/null 2>&1; then
    MISSING_PKGS+=("python-tidalapi")
fi

# Detección y recomendación de Kitty
if command -v kitty >/dev/null 2>&1; then
    echo -e "  ${GREEN}✔ Terminal Kitty detectada (soporte nativo de carátulas kitten icat).${RESET}"
else
    echo -e "  ${YELLOW}! Aviso: Kitty no está instalada.${RESET}"
    echo -e "    Quick-Tide utiliza el protocolo gráfico de Kitty para mostrar las carátulas en alta resolución."
    MISSING_PKGS+=("kitty")
fi

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo -e "\n  ${YELLOW}! Paquetes sugeridos o faltantes detectados:${RESET} ${MISSING_PKGS[*]}"
    if command -v pacman >/dev/null 2>&1; then
        read -rp "  ¿Deseas intentar instalarlos ahora con pacman? [S/n]: " inst_deps
        inst_deps=${inst_deps:-S}
        if [[ "$inst_deps" =~ ^[sS]$ ]]; then
            sudo pacman -S --needed --noconfirm "${MISSING_PKGS[@]}" || {
                echo -e "  ${YELLOW}No se pudieron instalar todos automáticamente. Asegúrate de instalarlos manualmente.${RESET}"
            }
        fi
    elif command -v apt >/dev/null 2>&1; then
        echo -e "  En distribuciones basadas en Debian/Ubuntu, puedes instalarlos con:"
        echo -e "  ${CYAN}sudo apt install python3-pyqt6 mpv cava kitty${RESET}"
    elif command -v dnf >/dev/null 2>&1; then
        echo -e "  En Fedora, puedes instalarlos con:"
        echo -e "  ${CYAN}sudo dnf install python3-pyqt6 mpv cava kitty${RESET}"
    fi
else
    echo -e "  ${GREEN}✔ Todas las dependencias principales están instaladas (Python, PyQt6, MPV, CAVA, Kitty).${RESET}"
fi

# 2. Comprobar servicios de música y sesión
echo -e "\n${BLUE}==> 2. Comprobando servicios de música...${RESET}"
LOWTIDE_SESSION="$HOME/.config/low-tide/session.json"
QUICKTIDE_SESSION="$HOME/.config/quick-tide/session.json"

echo -e "  ${GREEN}✔ YouTube Music:${RESET} Listo para usar inmediatamente sin cuenta (streaming Opus Hi-Fi)."
if [ -f "$QUICKTIDE_SESSION" ] || [ -f "$LOWTIDE_SESSION" ]; then
    echo -e "  ${GREEN}✔ Tidal Hi-Fi:${RESET} Sesión activa detectada (autenticación nativa lista)."
else
    echo -e "  ${CYAN}• Tidal Hi-Fi:${RESET} Autenticación nativa integrada disponible."
    echo -e "    Al abrir el programa podrás iniciar sesión en Tidal directamente desde tu navegador con un clic."
fi

# 3. Instalación de archivos y recursos
echo -e "\n${BLUE}==> 3. Instalando archivos y recursos...${RESET}"
TARGET_SHARE="$HOME/.local/share/quick-tide"
BIN_DIR="$HOME/.local/bin"

mkdir -p "$BIN_DIR"
mkdir -p "$TARGET_SHARE/bin"
mkdir -p "$TARGET_SHARE/sounds"
mkdir -p "$HOME/.local/share/applications"

# Copiar ejecutables y módulos a share
cp -f "$DIR/Main.qml" "$TARGET_SHARE/Main.qml"
cp -f "$DIR/player_tui.py" "$TARGET_SHARE/player_tui.py"
cp -f "$DIR/search_gui.py" "$TARGET_SHARE/search_gui.py"
cp -f "$DIR/scrobbler.py" "$TARGET_SHARE/scrobbler.py"
cp -f "$DIR/tidal_backend.py" "$TARGET_SHARE/tidal_backend.py"
cp -f "$DIR/tidal_client.py" "$TARGET_SHARE/tidal_client.py"
cp -f "$DIR/ytmusic_backend.py" "$TARGET_SHARE/ytmusic_backend.py"
cp -f "$DIR/music_backend.py" "$TARGET_SHARE/music_backend.py"
cp -f "$DIR/lyrics.py" "$TARGET_SHARE/lyrics.py"
cp -f "$DIR/config.py" "$TARGET_SHARE/config.py"
if [ -f "$DIR/CHANGELOG.md" ]; then
    cp -f "$DIR/CHANGELOG.md" "$TARGET_SHARE/CHANGELOG.md"
fi

# Copiar wrappers de binarios
cp -rf "$DIR/bin/"* "$TARGET_SHARE/bin/"
chmod +x "$TARGET_SHARE/bin/"*

# Copiar assets de sonido integrados en el repositorio
if [ -d "$DIR/assets/sounds" ]; then
    cp -rf "$DIR/assets/sounds/"* "$TARGET_SHARE/sounds/"
    echo -e "  ${GREEN}✔ Efectos de sonido integrados instalados en ~/.local/share/quick-tide/sounds/${RESET}"
fi

# Copiar iconos y assets
if [ -d "$DIR/assets/icons" ]; then
    mkdir -p "$TARGET_SHARE/assets/icons"
    cp -rf "$DIR/assets/icons/"* "$TARGET_SHARE/assets/icons/"
fi

# Enlazar ejecutables en ~/.local/bin
ln -sf "$TARGET_SHARE/bin/tidal-search-gui" "$BIN_DIR/tidal-search-gui"
ln -sf "$TARGET_SHARE/bin/tidal-player-tui" "$BIN_DIR/tidal-player-tui"
ln -sf "$BIN_DIR/tidal-search-gui" "$BIN_DIR/quick-tide"
ln -sf "$BIN_DIR/tidal-player-tui" "$BIN_DIR/quick-tide-player"
ln -sf "$DIR/update.sh" "$BIN_DIR/quick-tide-update"

# Compatibilidad con enlace histórico ~/.local/share/tidal-gui
if [ ! -e "$HOME/.local/share/tidal-gui" ]; then
    ln -sf "$TARGET_SHARE" "$HOME/.local/share/tidal-gui" 2>/dev/null || true
fi

# Instalar accesos directos de escritorio
if [ -d "$DIR/desktop" ]; then
    cp -f "$DIR/desktop/"*.desktop "$HOME/.local/share/applications/" 2>/dev/null || true
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    fi
    echo -e "  ${GREEN}✔ Accesos directos de escritorio registrados en ~/.local/share/applications/${RESET}"
fi

echo -e "  ${GREEN}✔ Binarios instalados en ~/.local/bin/ (quick-tide, quick-tide-player)${RESET}"

# 4. Inicializar archivo de configuración
echo -e "\n${BLUE}==> 4. Inicializando configuración en ~/.config/quick-tide/...${RESET}"
mkdir -p "$HOME/.config/quick-tide"
if [ ! -f "$HOME/.config/quick-tide/config.toml" ] && [ ! -f "$HOME/.config/quick-tide/config" ]; then
    python3 "$DIR/config.py" >/dev/null 2>&1 || true
    echo -e "  ${GREEN}✔ Archivo de configuración creado: ~/.config/quick-tide/config.toml${RESET}"
else
    echo -e "  ${GREEN}✔ Configuración existente conservada en ~/.config/quick-tide/config.toml${RESET}"
fi

# 5. Detección de entorno y configuración de atajo de teclado
echo -e "\n${BLUE}==> 5. Configuración de atajos de teclado y reglas de ventana...${RESET}"

normalize_keybind() {
    local raw="$1"
    python3 -c '
import sys, re
raw = sys.argv[1].strip() if len(sys.argv) > 1 and sys.argv[1].strip() else "SUPER + T"
tokens = [t.strip().upper() for t in re.split(r"[\s+,]+", raw) if t.strip()]
mods = []
key = None
for tok in tokens:
    if tok in ("SUPER", "WIN", "WINDOWS", "MOD4", "SUPR"):
        mods.append("SUPER")
    elif tok in ("SHIFT", "SHFT"):
        mods.append("SHIFT")
    elif tok in ("CTRL", "CONTROL"):
        mods.append("CTRL")
    elif tok in ("ALT", "MOD1"):
        mods.append("ALT")
    else:
        key = tok.upper() if len(tok) == 1 else tok.capitalize()

if not key:
    key = "T"
if not mods:
    mods = ["SUPER"]

seen = set()
uniq_mods = [m for m in mods if not (m in seen or seen.add(m))]

lua_str = " + ".join(uniq_mods + [key])
hypr_str = " ".join(uniq_mods) + ", " + key
kde_mods = [m.replace("SUPER", "Meta").capitalize() for m in uniq_mods]
kde_str = "+".join(kde_mods + [key])
sway_mods = ["$mod" if m == "SUPER" else m.lower() for m in uniq_mods]
sway_str = "+".join(sway_mods + [key.lower()])

print(f"{lua_str};{hypr_str};{kde_str};{sway_str}")
' "$raw" 2>/dev/null || echo "SUPER + T;SUPER, T;Meta+T;\$mod+t"
}

CURRENT_DESKTOP="desconocido"
if [ -n "$KDE_FULL_SESSION" ] || [ "$XDG_CURRENT_DESKTOP" = "KDE" ] || [ "$DESKTOP_SESSION" = "plasma" ]; then
    CURRENT_DESKTOP="kde"
elif [ "$XDG_CURRENT_DESKTOP" = "GNOME" ] || [ "$DESKTOP_SESSION" = "gnome" ]; then
    CURRENT_DESKTOP="gnome"
elif [ -n "$HYPRLAND_INSTANCE_SIGNATURE" ] || [ "$XDG_CURRENT_DESKTOP" = "Hyprland" ]; then
    CURRENT_DESKTOP="hyprland"
elif [ -n "$SWAYSOCK" ] || [ "$XDG_CURRENT_DESKTOP" = "sway" ]; then
    CURRENT_DESKTOP="sway"
elif [ -n "$NIRI_SOCKET" ] || [ "$XDG_CURRENT_DESKTOP" = "niri" ]; then
    CURRENT_DESKTOP="niri"
fi

echo -e "  Entorno de escritorio detectado: ${CYAN}${CURRENT_DESKTOP}${RESET}"

DEFAULT_KEY="SUPER + T"
if [ "$CURRENT_DESKTOP" = "kde" ]; then
    DEFAULT_KEY="Meta+Shift+T"
fi

echo ""
echo -e "  ${PURPLE}╭──────────────────────────────────────────────────────────────────╮${RESET}"
echo -e "  ${PURPLE}│${RESET} ⌨️   ${BOLD}¿Cómo escribir tu combinación de teclas?${RESET}                       ${PURPLE}│${RESET}"
echo -e "  ${PURPLE}│${RESET} • Puedes usar el signo '+' o comas, mayúsculas o minúsculas.      ${PURPLE}│${RESET}"
echo -e "  ${PURPLE}│${RESET} • Tecla Windows / Super: escribe ${CYAN}SUPER${RESET} (o Win / Supr).             ${PURPLE}│${RESET}"
echo -e "  ${PURPLE}│${RESET} • Modificadores disponibles: ${CYAN}SUPER${RESET}, ${CYAN}ALT${RESET}, ${CYAN}CTRL${RESET}, ${CYAN}SHIFT${RESET}.            ${PURPLE}│${RESET}"
echo -e "  ${PURPLE}│${RESET} • Ejemplos habituales:                                            ${PURPLE}│${RESET}"
echo -e "  ${PURPLE}│${RESET}     1) ${GREEN}SUPER + T${RESET}          (Tecla Windows + T)                     ${PURPLE}│${RESET}"
echo -e "  ${PURPLE}│${RESET}     2) ${GREEN}SUPER + SHIFT + T${RESET}  (Tecla Windows + Shift + T)             ${PURPLE}│${RESET}"
echo -e "  ${PURPLE}│${RESET}     3) ${GREEN}ALT + SPACE${RESET}        (Tecla Alt + Barra espaciadora)         ${PURPLE}│${RESET}"
echo -e "  ${PURPLE}│${RESET}     4) Presionar [Enter]   (Usa el recomendado: ${BOLD}${DEFAULT_KEY}${RESET})        ${PURPLE}│${RESET}"
echo -e "  ${PURPLE}╰──────────────────────────────────────────────────────────────────╯${RESET}"
echo ""

read -rp "  ¿Deseas configurar el atajo de teclado global ahora? [S/n]: " set_key
set_key=${set_key:-S}

if [[ "$set_key" =~ ^[sS]$ ]]; then
    read -rp "  Ingresa la combinación deseada [Default: $DEFAULT_KEY]: " RAW_USER_KEY
    RAW_USER_KEY="${RAW_USER_KEY:-$DEFAULT_KEY}"

    PARSED_KEYS=$(normalize_keybind "$RAW_USER_KEY")
    KEY_LUA=$(echo "$PARSED_KEYS" | cut -d';' -f1)
    KEY_HYPR=$(echo "$PARSED_KEYS" | cut -d';' -f2)
    KEY_KDE=$(echo "$PARSED_KEYS" | cut -d';' -f3)
    KEY_SWAY=$(echo "$PARSED_KEYS" | cut -d';' -f4)

    echo -e "  ${GREEN}✔ Atajo normalizado:${RESET} ${CYAN}${KEY_LUA}${RESET}"

    case "$CURRENT_DESKTOP" in
        kde)
            KCONF=$(command -v kwriteconfig6 || command -v kwriteconfig5 || true)
            if [ -n "$KCONF" ]; then
                $KCONF --file kglobalshortcutsrc --group "quick-tide.desktop" --key "_launch" "${KEY_KDE},none,Quick-Tide (Buscador Tidal)"
                qdbus6 org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel.reloadConfig 2>/dev/null || \
                qdbus org.kde.kglobalaccel /kglobalaccel org.kde.KGlobalAccel.reloadConfig 2>/dev/null || true
                echo -e "  ${GREEN}✔ Atajo '$KEY_KDE' registrado en KDE Plasma (kglobalshortcutsrc).${RESET}"
            else
                echo -e "  ${YELLOW}Abre 'Preferencias del Sistema > Accesos rápidos', busca 'Quick-Tide' y asígnale '$KEY_KDE'.${RESET}"
            fi
            ;;
        hyprland)
            CONFIGURED=0
            # 1. Omarchy / Modular Lua Hyprland setup
            if [ -f "$HOME/.config/hypr/config/keybinds.lua" ] && [ -f "$HOME/.config/hypr/config/settings.lua" ]; then
                if ! grep -q "tidal-search-gui" "$HOME/.config/hypr/config/keybinds.lua" 2>/dev/null; then
                    echo "hl.bind(\"$KEY_LUA\", hl.dsp.exec_cmd(\"tidal-search-gui\"))" >> "$HOME/.config/hypr/config/keybinds.lua"
                fi
                if ! grep -q "tidal-search-gui" "$HOME/.config/hypr/config/settings.lua" 2>/dev/null; then
                    cat <<'HL' >> "$HOME/.config/hypr/config/settings.lua"

-- Quick-Tide window rules
hl.window_rule({
  name = "tidal-search-gui",
  match = { class = "tidal-search-gui" },
  float = true,
  center = true,
  size = { 740, 560 },
})

hl.window_rule({
  name = "tidal-player-tui",
  match = { class = "tidal-player-tui" },
  float = true,
  center = true,
  size = { 1100, 680 },
})
HL
                fi
                CONFIGURED=1
            # 2. Archcraft / bindings.lua setup
            elif [ -f "$HOME/.config/hypr/bindings.lua" ]; then
                if ! grep -q "tidal-search-gui" "$HOME/.config/hypr/bindings.lua" 2>/dev/null; then
                    echo "hl.bind(\"$KEY_LUA\", hl.dsp.exec_cmd(\"tidal-search-gui\"))" >> "$HOME/.config/hypr/bindings.lua"
                fi
                CONFIGURED=1
            # 3. Standard hyprland.conf setup
            elif [ -f "$HOME/.config/hypr/hyprland.conf" ]; then
                if ! grep -q "tidal-search-gui" "$HOME/.config/hypr/hyprland.conf" 2>/dev/null; then
                    cat <<HLC >> "$HOME/.config/hypr/hyprland.conf"

# Quick-Tide
bind = $KEY_HYPR, exec, tidal-search-gui
windowrulev2 = float, class:^(tidal-search-gui)$
windowrulev2 = center, class:^(tidal-search-gui)$
windowrulev2 = size 740 560, class:^(tidal-search-gui)$
windowrulev2 = float, class:^(tidal-player-tui)$
windowrulev2 = center, class:^(tidal-player-tui)$
windowrulev2 = size 1100 680, class:^(tidal-player-tui)$
HLC
                fi
                CONFIGURED=1
            fi

            if [ $CONFIGURED -eq 1 ]; then
                if command -v hyprctl >/dev/null 2>&1; then
                    hyprctl reload >/dev/null 2>&1 || true
                fi
                echo -e "  ${GREEN}✔ Atajo '$KEY_LUA' y reglas de ventana flotante configuradas y recargadas en Hyprland.${RESET}"
            else
                echo -e "\n  ${PURPLE}╭──────────────────────────────────────────────────────────────╮${RESET}"
                echo -e "  ${PURPLE}│${RESET} 📋 ${BOLD}Instrucciones para configurar manualmente en Hyprland:${RESET}     ${PURPLE}│${RESET}"
                echo -e "  ${PURPLE}╰──────────────────────────────────────────────────────────────╯${RESET}"
                echo -e "  • En ${CYAN}~/.config/hypr/hyprland.conf${RESET} añade:"
                echo -e "      ${GREEN}bind = $KEY_HYPR, exec, tidal-search-gui${RESET}"
                echo -e "      ${GREEN}windowrulev2 = float, class:^(tidal-search-gui)$${RESET}"
                echo -e "      ${GREEN}windowrulev2 = size 740 560, class:^(tidal-search-gui)$${RESET}"
                echo -e "      ${GREEN}windowrulev2 = center, class:^(tidal-search-gui)$${RESET}"
                echo -e "      ${GREEN}windowrulev2 = float, class:^(tidal-player-tui)$${RESET}"
                echo -e "      ${GREEN}windowrulev2 = size 1100 680, class:^(tidal-player-tui)$${RESET}"
                echo -e "      ${GREEN}windowrulev2 = center, class:^(tidal-player-tui)$${RESET}\n"
                echo -e "  • O si usas configuración modular en Lua (${CYAN}keybinds.lua${RESET}):"
                echo -e "      ${GREEN}hl.bind(\"$KEY_LUA\", hl.dsp.exec_cmd(\"tidal-search-gui\"))${RESET}\n"
            fi
            ;;
        gnome)
            echo -e "\n  ${PURPLE}╭──────────────────────────────────────────────────────────────╮${RESET}"
            echo -e "  ${PURPLE}│${RESET} 📋 ${BOLD}Configuración de atajo en GNOME:${RESET}                           ${PURPLE}│${RESET}"
            echo -e "  ${PURPLE}╰──────────────────────────────────────────────────────────────╯${RESET}"
            echo -e "  1. Ve a ${CYAN}Configuración > Teclado > Ver y personalizar atajos > Atajos personalizados${RESET}."
            echo -e "  2. Añade un nuevo atajo:"
            echo -e "     • Nombre:  ${BOLD}Quick-Tide${RESET}"
            echo -e "     • Comando: ${CYAN}tidal-search-gui${RESET}"
            echo -e "     • Tecla:   ${CYAN}$KEY_LUA${RESET}\n"
            ;;
        sway|i3)
            echo -e "\n  ${PURPLE}╭──────────────────────────────────────────────────────────────╮${RESET}"
            echo -e "  ${PURPLE}│${RESET} 📋 ${BOLD}Configuración para Sway / i3 (~/.config/sway/config):${RESET}      ${PURPLE}│${RESET}"
            echo -e "  ${PURPLE}╰──────────────────────────────────────────────────────────────╯${RESET}"
            echo -e "  Añade la siguiente línea a tu archivo de configuración:"
            echo -e "      ${GREEN}bindsym $KEY_SWAY exec tidal-search-gui${RESET}\n"
            ;;
        niri)
            echo -e "\n  ${PURPLE}╭──────────────────────────────────────────────────────────────╮${RESET}"
            echo -e "  ${PURPLE}│${RESET} 📋 ${BOLD}Configuración para Niri (~/.config/niri/config.kdl):${RESET}       ${PURPLE}│${RESET}"
            echo -e "  ${PURPLE}╰──────────────────────────────────────────────────────────────╯${RESET}"
            echo -e "  Añade el bloque:"
            echo -e "      ${GREEN}binds { Mod+T { spawn \"tidal-search-gui\"; } }${RESET}\n"
            ;;
        *)
            echo -e "\n  ${PURPLE}╭──────────────────────────────────────────────────────────────╮${RESET}"
            echo -e "  ${PURPLE}│${RESET} 📋 ${BOLD}Atajo manual para tu gestor de ventanas:${RESET}                  ${PURPLE}│${RESET}"
            echo -e "  ${PURPLE}╰──────────────────────────────────────────────────────────────╯${RESET}"
            echo -e "  Asigna la combinación ${CYAN}$KEY_LUA${RESET} al comando ${CYAN}tidal-search-gui${RESET}.\n"
            ;;
    esac
else
    echo -e "\n  ${YELLOW}Configuración automática omitida.${RESET}"
    echo -e "  ${PURPLE}╭──────────────────────────────────────────────────────────────╮${RESET}"
    echo -e "  ${PURPLE}│${RESET} 📋 ${BOLD}Instrucciones manuales para cuando quieras configurarlo:${RESET}    ${PURPLE}│${RESET}"
    echo -e "  ${PURPLE}╰──────────────────────────────────────────────────────────────╯${RESET}"
    echo -e "  • ${BOLD}Hyprland (hyprland.conf):${RESET}"
    echo -e "      ${GREEN}bind = SUPER, T, exec, tidal-search-gui${RESET}"
    echo -e "      ${GREEN}windowrulev2 = float, class:^(tidal-search-gui)$${RESET}"
    echo -e "      ${GREEN}windowrulev2 = size 740 560, class:^(tidal-search-gui)$${RESET}"
    echo -e "      ${GREEN}windowrulev2 = center, class:^(tidal-search-gui)$${RESET}"
    echo -e "      ${GREEN}windowrulev2 = float, class:^(tidal-player-tui)$${RESET}"
    echo -e "      ${GREEN}windowrulev2 = size 1100 680, class:^(tidal-player-tui)$${RESET}"
    echo -e "  • ${BOLD}Hyprland (Lua / keybinds.lua):${RESET}"
    echo -e "      ${GREEN}hl.bind(\"SUPER + T\", hl.dsp.exec_cmd(\"tidal-search-gui\"))${RESET}"
    echo -e "  • ${BOLD}Sway / i3:${RESET}"
    echo -e "      ${GREEN}bindsym \$mod+t exec tidal-search-gui${RESET}"
    echo -e "  • ${BOLD}KDE / GNOME:${RESET}"
    echo -e "      Comando: ${CYAN}tidal-search-gui${RESET} | Tecla sugerida: ${CYAN}SUPER + T${RESET}\n"
fi

# 6. Finalización
echo -e "\n${GREEN}${BOLD}✔ ¡Instalación de Quick-Tide finalizada con éxito!${RESET}"
echo -e "Puedes abrirlo desde:"
echo -e "  1. La terminal ejecutando: ${CYAN}quick-tide${RESET} (o ${CYAN}tidal-search-gui${RESET})"
echo -e "  2. El reproductor directo: ${CYAN}quick-tide-player${RESET} (o ${CYAN}tidal-player-tui${RESET})"
echo -e "  3. El menú de aplicaciones de tu escritorio buscando: ${CYAN}Quick-Tide${RESET}"
if [ -n "$CHOSEN_KEY" ]; then
    echo -e "  4. Con tu atajo de teclado: ${CYAN}$CHOSEN_KEY${RESET}"
fi
echo ""
echo -e "${BLUE}Tip de Last.fm:${RESET} Para sincronizar tus scrobbles, ejecuta: ${CYAN}tidal-player-tui --setup-lastfm${RESET}"
echo ""

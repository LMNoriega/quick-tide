#!/usr/bin/env bash
# ==============================================================================
# Quick-Tide - Installer & Setup Script
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}=== Instalador de Quick-Tide (Tidal Serpantinum Suite) ===${NC}\n"

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
LOWTIDE_DIR="$HOME/.local/share/low-tide"
LOWTIDE_SESSION="$HOME/.config/low-tide/session.json"

mkdir -p "$BIN_DIR"

# 1. Comprobar dependencias del sistema
echo -e "${BLUE}1. Comprobando dependencias del sistema...${NC}"

check_cmd() {
    if command -v "$1" >/dev/null 2>&1; then
        echo -e "  [${GREEN}✓${NC}] $1 detectado: $(command -v "$1")"
    else
        echo -e "  [${YELLOW}!${NC}] $1 no encontrado. (Recomendado para: $2)"
    fi
}

check_cmd "kitty" "Carátulas nativas en terminal y visualización TUI"
check_cmd "mpv" "Reproducción de streams Hi-Fi y control IPC"
check_cmd "cava" "Visualizador de espectro de audio en tiempo real"
check_cmd "python3" "Entorno base de ejecución"

# Comprobar PyQt6
if python3 -c "import PyQt6" >/dev/null 2>&1; then
    echo -e "  [${GREEN}✓${NC}] PyQt6 detectado en python3 del sistema"
else
    echo -e "  [${RED}✗${NC}] PyQt6 no encontrado. Instálalo con: sudo pacman -S python-pyqt6 (o pip install PyQt6)"
fi

# 2. Comprobar integración con low-tide (proveedor de sesión y OAuth de Tidal)
echo -e "\n${BLUE}2. Comprobando sesión de Tidal (low-tide)...${NC}"
if [ -f "$LOWTIDE_SESSION" ]; then
    echo -e "  [${GREEN}✓${NC}] Sesión de Tidal detectada en: $LOWTIDE_SESSION"
else
    echo -e "  [${YELLOW}!${NC}] No se encontró sesión activa de Tidal en: $LOWTIDE_SESSION"
    echo -e "      ${BOLD}¿Cómo iniciar sesión?${NC}"
    echo -e "      1. Si no tienes low-tide descargado:"
    echo -e "         git clone https://github.com/mrusme/low-tide.git ~/.local/share/low-tide"
    echo -e "         cd ~/.local/share/low-tide && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    echo -e "      2. Ejecuta low-tide una única vez para iniciar sesión con Tidal vía OAuth:"
    echo -e "         python -m lowtide"
    echo -e "      3. Abre el enlace en tu navegador, confirma el inicio de sesión y sal de low-tide."
    echo -e "      ¡Listo! Tidal Suite reutilizará esa sesión de manera automática."
fi

# 3. Instalar ejecutables en ~/.local/bin
echo -e "\n${BLUE}3. Vinculando ejecutables en $BIN_DIR...${NC}"
chmod +x "$INSTALL_DIR/bin/"*
ln -sf "$INSTALL_DIR/bin/tidal-search-gui" "$BIN_DIR/tidal-search-gui"
ln -sf "$INSTALL_DIR/bin/tidal-player-tui" "$BIN_DIR/tidal-player-tui"
ln -sf "$INSTALL_DIR/bin/tidal-search-gui" "$BIN_DIR/quick-tide"
ln -sf "$INSTALL_DIR/bin/tidal-player-tui" "$BIN_DIR/quick-tide-player"
echo -e "  [${GREEN}✓${NC}] quick-tide / tidal-search-gui -> $BIN_DIR/quick-tide"
# 4. Inicializar configuración en ~/.config/quick-tide
echo -e "\n${BLUE}4. Comprobando configuración en ~/.config/quick-tide/...${NC}"
mkdir -p "$HOME/.config/quick-tide"
if [ ! -f "$HOME/.config/quick-tide/config.toml" ] && [ ! -f "$HOME/.config/quick-tide/config" ]; then
    python3 "$INSTALL_DIR/config.py" >/dev/null 2>&1 || true
    echo -e "  [${GREEN}✓${NC}] Configuración inicial creada: $HOME/.config/quick-tide/config.toml"
else
    echo -e "  [${GREEN}✓${NC}] Configuración existente detectada en $HOME/.config/quick-tide/"
fi

# 5. Instrucciones para Hyprland
echo -e "\n${BOLD}${GREEN}✔ Instalación completada con éxito.${NC}"
echo -e "\n${BOLD}Atajo recomendado para Hyprland (~/.config/hypr/hyprland.conf):${NC}"
echo -e "  bind = \$mainMod, T, exec, tidal-search-gui\n"
echo -e "${BOLD}Reglas de ventana recomendadas para Hyprland:${NC}"
echo -e "  windowrulev2 = float, class:^(tidal-search-gui)$"
echo -e "  windowrulev2 = size 740 560, class:^(tidal-search-gui)$"
echo -e "  windowrulev2 = center, class:^(tidal-search-gui)$"
echo -e "  windowrulev2 = stayfocused, class:^(tidal-search-gui)$"
echo -e "  windowrulev2 = dimaround, class:^(tidal-search-gui)$\n"

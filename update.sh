#!/usr/bin/env bash
# ==============================================================================
# Quick-Tide - Actualizador Inteligente
# ==============================================================================
REAL_SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(cd "$(dirname "$REAL_SCRIPT")" && pwd)"

# Si se ejecuta desde un symlink global, buscar el repositorio con git
if [ ! -d "$DIR/.git" ]; then
    if [ -d "$HOME/Projects/tidal-gui/.git" ]; then
        DIR="$HOME/Projects/tidal-gui"
    elif [ -d "$HOME/.local/share/quick-tide/.git" ]; then
        DIR="$HOME/.local/share/quick-tide"
    fi
fi

exec "$DIR/install.sh" --update "$@"

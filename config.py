#!/usr/bin/env python3
"""
Quick-Tide Configuration Manager
Handles reading, writing, and validating settings from ~/.config/quick-tide/config.toml
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

CONFIG_DIR = Path.home() / ".config" / "quick-tide"
CONFIG_FILE = CONFIG_DIR / "config.toml"
ALT_CONFIG_FILE = CONFIG_DIR / "config"

DEFAULT_CONFIG_CONTENT = """# Quick-Tide Configuration File
# Location: ~/.config/quick-tide/config.toml

# Stream quality: "low", "high", "lossless", "max"
# Default: "lossless"
# Note: "max" requires a TIDAL Max subscription.
quality = "lossless"

# Crossfade duration in seconds when crossfade is enabled (toggle with 'x' in player).
# Default: 5
# Note: Crossfade is always OFF at startup regardless of this value.
crossfade = 5
"""

DEFAULT_CONFIG: Dict[str, Any] = {
    "quality": "lossless",
    "crossfade": 5,
}

VALID_QUALITIES = ("low", "high", "lossless", "max")


def ensure_config_exists() -> Path:
    """Ensure ~/.config/quick-tide exists and has a config.toml file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.is_file() and not ALT_CONFIG_FILE.is_file():
        try:
            CONFIG_FILE.write_text(DEFAULT_CONFIG_CONTENT, encoding="utf-8")
        except Exception:
            pass
        return CONFIG_FILE
    if CONFIG_FILE.is_file():
        return CONFIG_FILE
    return ALT_CONFIG_FILE


def _parse_toml_fallback(text: str) -> Dict[str, Any]:
    """Fallback line-based key = value parser if tomllib is unavailable."""
    data: Dict[str, Any] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.split("#")[0].strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            elif v.isdigit():
                v = int(v)
            elif v.lower() == "true":
                v = True
            elif v.lower() == "false":
                v = False
            data[k] = v
    return data


def load_config() -> Dict[str, Any]:
    """Load configuration from ~/.config/quick-tide/config.toml (or config).
    Returns a dictionary with parsed options, falling back to defaults for missing keys."""
    cfg_path = ensure_config_exists()
    raw_data: Dict[str, Any] = {}

    if cfg_path.is_file():
        try:
            content = cfg_path.read_text(encoding="utf-8")
            try:
                import tomllib
                raw_data = tomllib.loads(content)
            except Exception:
                raw_data = _parse_toml_fallback(content)
        except Exception:
            raw_data = {}

    # Start with defaults, update with user configuration
    result = dict(DEFAULT_CONFIG)
    result.update(raw_data)

    # Validate quality
    q = str(result.get("quality", "lossless")).lower().strip()
    if q not in VALID_QUALITIES:
        q = "lossless"
    result["quality"] = q

    # Validate crossfade
    try:
        cf = int(result.get("crossfade", 5))
        if cf < 0:
            cf = 0
    except (ValueError, TypeError):
        cf = 5
    result["crossfade"] = cf

    return result


def get_quality() -> str:
    """Get validated stream quality setting."""
    return str(load_config().get("quality", "lossless"))


def get_crossfade() -> int:
    """Get validated crossfade duration in seconds."""
    return int(load_config().get("crossfade", 5))

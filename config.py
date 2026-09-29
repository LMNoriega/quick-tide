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

# Main streaming service: "tidal" (Hi-Res FLAC / OAuth) or "youtube" (Opus / zero login)
service = "tidal"

# First-run setup completed flag
setup_completed = true

# Stream quality: "low", "high", "lossless", "max"
# Default: "lossless"
# Note: "max" requires a TIDAL Max subscription.
quality = "lossless"

# Crossfade duration in seconds when crossfade is enabled (toggle with 'x' in player).
# Default: 5
# Note: Crossfade is always OFF at startup regardless of this value.
crossfade = 5

[lastfm]
# Set enabled = true to activate Last.fm scrobbling and Now Playing updates
enabled = false
username = ""
password = ""          # Plaintext password (auto-hashed) or leave blank if using password_hash
password_hash = ""     # MD5 hash of your password (generated automatically if password is provided)
api_key = ""           # Last.fm API Key (from https://www.last.fm/api/account/create)
api_secret = ""        # Last.fm API Secret
session_key = ""       # Optional Last.fm session key
"""

DEFAULT_CONFIG: Dict[str, Any] = {
    "service": "tidal",
    "setup_completed": False,
    "quality": "lossless",
    "crossfade": 5,
    "lastfm": {
        "enabled": False,
        "username": "",
        "password": "",
        "password_hash": "",
        "api_key": "",
        "api_secret": "",
        "session_key": "",
    },
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
    current_section = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            if current_section not in data:
                data[current_section] = {}
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
            if current_section:
                data[current_section][k] = v
            else:
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
    result = {
        "service": raw_data.get("service", DEFAULT_CONFIG["service"]),
        "setup_completed": raw_data.get("setup_completed", DEFAULT_CONFIG["setup_completed"]),
        "quality": DEFAULT_CONFIG["quality"],
        "crossfade": DEFAULT_CONFIG["crossfade"],
        "lastfm": dict(DEFAULT_CONFIG["lastfm"]),
    }
    if "quality" in raw_data:
        result["quality"] = raw_data["quality"]
    if "crossfade" in raw_data:
        result["crossfade"] = raw_data["crossfade"]
    if "lastfm" in raw_data and isinstance(raw_data["lastfm"], dict):
        result["lastfm"].update(raw_data["lastfm"])

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

    # Check and merge environment variable overrides for Last.fm
    lfm = result["lastfm"]
    env_enabled = os.environ.get("LASTFM_ENABLED")
    if env_enabled is not None:
        lfm["enabled"] = env_enabled.lower() in ("1", "true", "yes", "on")
    if os.environ.get("LASTFM_USERNAME"):
        lfm["username"] = os.environ["LASTFM_USERNAME"]
    if os.environ.get("LASTFM_PASSWORD"):
        lfm["password"] = os.environ["LASTFM_PASSWORD"]
    if os.environ.get("LASTFM_PASSWORD_HASH"):
        lfm["password_hash"] = os.environ["LASTFM_PASSWORD_HASH"]
    if os.environ.get("LASTFM_API_KEY"):
        lfm["api_key"] = os.environ["LASTFM_API_KEY"]
    if os.environ.get("LASTFM_API_SECRET"):
        lfm["api_secret"] = os.environ["LASTFM_API_SECRET"]
    if os.environ.get("LASTFM_SESSION_KEY"):
        lfm["session_key"] = os.environ["LASTFM_SESSION_KEY"]

    # Compute password_hash automatically if password is provided but hash is missing
    if lfm.get("password") and not lfm.get("password_hash"):
        import hashlib
        lfm["password_hash"] = hashlib.md5(lfm["password"].encode("utf-8")).hexdigest()

    return result


def get_active_service() -> str:
    """Returns 'tidal' or 'youtube'."""
    val = str(load_config().get("service", "tidal")).lower().strip()
    if val in ("youtube", "yt", "ytmusic"):
        return "youtube"
    return "tidal"


def set_active_service(service: str) -> bool:
    """Update active service in config.toml."""
    try:
        service = "youtube" if service in ("youtube", "yt", "ytmusic") else "tidal"
        cfg = load_config()
        cfg["service"] = service
        cfg["setup_completed"] = True
        return save_full_config(cfg)
    except Exception:
        return False


def is_setup_completed() -> bool:
    """Returns True if user has completed onboarding or has an active session."""
    cfg = load_config()
    if cfg.get("setup_completed", False):
        return True
    if (CONFIG_DIR / "session.json").is_file() or (Path.home() / ".config" / "low-tide" / "session.json").is_file():
        return True
    return False


def set_setup_completed(val: bool = True) -> bool:
    cfg = load_config()
    cfg["setup_completed"] = bool(val)
    return save_full_config(cfg)


def save_full_config(cfg: Dict[str, Any]) -> bool:
    """Save full configuration to ~/.config/quick-tide/config.toml."""
    try:
        cfg_path = ensure_config_exists()
        service = cfg.get("service", "tidal")
        setup_completed = str(cfg.get("setup_completed", True)).lower()
        quality = cfg.get("quality", "lossless")
        crossfade = cfg.get("crossfade", 5)

        lfm = cfg.get("lastfm", {})
        lfm_enabled = str(lfm.get("enabled", False)).lower()
        lfm_user = lfm.get("username", "")
        lfm_pass = lfm.get("password", "")
        lfm_hash = lfm.get("password_hash", "")
        lfm_key = lfm.get("api_key", "")
        lfm_sec = lfm.get("api_secret", "")
        lfm_ses = lfm.get("session_key", "")

        content = f"""# Quick-Tide Configuration File
# Location: ~/.config/quick-tide/config.toml

# Main streaming service: "tidal" (Hi-Res FLAC / OAuth) or "youtube" (Opus / zero login)
service = "{service}"

# First-run setup completed flag
setup_completed = {setup_completed}

# Stream quality: "low", "high", "lossless", "max"
quality = "{quality}"

# Crossfade duration in seconds when crossfade is enabled (toggle with 'x' in player).
crossfade = {crossfade}

[lastfm]
# Set enabled = true to activate Last.fm scrobbling and Now Playing updates
enabled = {lfm_enabled}
username = "{lfm_user}"
password = "{lfm_pass}"
password_hash = "{lfm_hash}"
api_key = "{lfm_key}"
api_secret = "{lfm_sec}"
session_key = "{lfm_ses}"
"""
        cfg_path.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False


def get_quality() -> str:
    """Get validated stream quality setting."""
    return str(load_config().get("quality", "lossless"))


def get_crossfade() -> int:
    """Get validated crossfade duration in seconds."""
    return int(load_config().get("crossfade", 5))


def get_lastfm_config() -> Dict[str, Any]:
    """Get validated Last.fm scrobbling configuration."""
    return dict(load_config().get("lastfm", {}))


def save_lastfm_config(
    username: str,
    api_key: str,
    api_secret: str,
    password_hash: str = "",
    password: str = "",
    session_key: str = "",
    enabled: bool = True
) -> bool:
    """Save or update the [lastfm] configuration block in ~/.config/quick-tide/config.toml."""
    try:
        cfg_path = ensure_config_exists()
        current_cfg = load_config()
        current_quality = current_cfg.get("quality", "lossless")
        current_crossfade = current_cfg.get("crossfade", 5)

        if password and not password_hash:
            import hashlib
            password_hash = hashlib.md5(password.encode("utf-8")).hexdigest()

        content = f"""# Quick-Tide Configuration File
# Location: ~/.config/quick-tide/config.toml

# Stream quality: "low", "high", "lossless", "max"
quality = "{current_quality}"

# Crossfade duration in seconds when crossfade is enabled (toggle with 'x' in player).
crossfade = {current_crossfade}

[lastfm]
# Set enabled = true to activate Last.fm scrobbling and Now Playing updates
enabled = {str(enabled).lower()}
username = "{username}"
password = "{password}"
password_hash = "{password_hash}"
api_key = "{api_key}"
api_secret = "{api_secret}"
session_key = "{session_key}"
"""
        cfg_path.write_text(content, encoding="utf-8")
        return True
    except Exception:
        return False

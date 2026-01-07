"""Configuration loading and parsing for cloud-mirror.

This module provides TOML configuration file parsing with support for:
- Default settings
- Named profiles for common source/destination pairs
- Relative path resolution from package location

Uses Python 3.11+ stdlib tomllib (no external dependencies).
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Configuration file parsing or loading error.

    Raised when:
    - TOML file not found
    - TOML syntax errors (includes line number)
    - Invalid configuration structure
    """

    pass


def parse_toml(config_path: Path) -> dict[str, Any]:
    """Parse TOML configuration file into structured dict.

    Extracts:
    - [defaults] section → config["defaults"]
    - [profiles.*] sections → config["profiles"][profile_name]
    - [rclone] section (optional) → config["rclone"]

    Args:
        config_path: Path to cloud-mirror.toml file

    Returns:
        Dict with keys:
            - "defaults": Dict of default configuration values
            - "profiles": Dict of profile name → profile config
            - "rclone": Dict of rclone-specific config (if present)

    Raises:
        ConfigError: If file not found, malformed TOML, or parse error

    Example:
        >>> config = parse_toml(Path("cloud-mirror.toml"))
        >>> config["defaults"]["transfers"]
        64
        >>> config["profiles"]["photos"]["remote"]
        'dropbox:photos'
    """
    # Check file exists
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    # Parse TOML
    try:
        with config_path.open("rb") as f:
            raw_config = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        # Include line number in error message for easier debugging
        raise ConfigError(
            f"Invalid TOML syntax in {config_path}: {e} (line {e.lineno})"
        ) from e
    except OSError as e:
        raise ConfigError(f"Failed to read config file {config_path}: {e}") from e

    # Extract sections
    defaults = raw_config.get("defaults", {})
    rclone_config = raw_config.get("rclone", {})

    # Extract profiles (all sections starting with "profiles.")
    profiles: dict[str, Any] = {}
    if "profiles" in raw_config:
        # TOML represents [profiles.name] as nested dict {"profiles": {"name": {...}}}
        profiles = raw_config["profiles"]

    return {
        "defaults": defaults,
        "profiles": profiles,
        "rclone": rclone_config,
    }

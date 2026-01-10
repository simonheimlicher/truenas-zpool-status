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


def find_config_file(package_dir: Path) -> Path | None:
    """Find cloud-mirror.toml config file relative to package location.

    Search order (first found wins):
    1. package_dir/cloud-mirror.toml (highest precedence)
    2. package_dir.parent/cloud-mirror.toml (installation directory)

    Args:
        package_dir: Path to the cloud_mirror package directory

    Returns:
        Path to config file if found, None if not found

    Example:
        >>> # Given: /opt/cloud-mirror/cloud_mirror/ package directory
        >>> # And: /opt/cloud-mirror/cloud-mirror.toml exists
        >>> config_path = find_config_file(Path("/opt/cloud-mirror/cloud_mirror"))
        >>> config_path
        Path('/opt/cloud-mirror/cloud-mirror.toml')

        >>> # Given: No config file exists
        >>> config_path = find_config_file(Path("/opt/cloud-mirror/cloud_mirror"))
        >>> config_path
        None
    """
    # Return None if package directory doesn't exist (graceful fallback)
    if not package_dir.exists():
        return None

    # Search order: package directory first, then parent
    search_locations = [
        package_dir / "cloud-mirror.toml",
        package_dir.parent / "cloud-mirror.toml",
    ]

    for config_path in search_locations:
        if config_path.exists():
            return config_path

    # No config found in any location
    return None


def merge_config(
    defaults: dict[str, Any],
    profile: dict[str, Any] | None,
    cli_args: dict[str, Any],
) -> dict[str, Any]:
    """Merge configuration from defaults, profile, and CLI arguments.

    Precedence order (later layers override earlier):
    1. defaults (lowest priority)
    2. profile
    3. cli_args (highest priority - always wins)

    Supports partial profiles where profile specifies only source or destination,
    with CLI args filling in the missing pieces.

    Args:
        defaults: Default configuration values from [defaults] section
        profile: Profile-specific config from [profiles.NAME], or None if no profile
        cli_args: Arguments provided via command line

    Returns:
        Merged configuration dict with precedence applied

    Example:
        >>> defaults = {"transfers": 32}
        >>> profile = {"transfers": 64, "source": "tank/photos"}
        >>> cli_args = {"destination": "dropbox:backup"}
        >>> merge_config(defaults, profile, cli_args)
        {'transfers': 64, 'source': 'tank/photos', 'destination': 'dropbox:backup'}

        >>> # CLI args override profile
        >>> cli_args = {"transfers": 128, "destination": "dropbox:backup"}
        >>> merge_config(defaults, profile, cli_args)
        {'transfers': 128, 'source': 'tank/photos', 'destination': 'dropbox:backup'}
    """
    # Start with defaults
    result = dict(defaults)

    # Merge profile if provided (overrides defaults)
    if profile is not None:
        result.update(profile)

    # Merge CLI args (overrides everything)
    result.update(cli_args)

    return result


def load_config(package_dir: Path) -> dict[str, Any]:
    """Load configuration from TOML file relative to package directory.

    Combines find_config_file() and parse_toml() to:
    1. Search for cloud-mirror.toml relative to package location
    2. Parse TOML if found
    3. Return parsed config structure

    Args:
        package_dir: Path to the cloud_mirror package directory

    Returns:
        Parsed config dict with "defaults" and "profiles" keys.
        Returns empty structure if no config file found.

    Raises:
        ConfigError: If config file found but malformed

    Example:
        >>> config = load_config(Path("/opt/cloud-mirror/cloud_mirror"))
        >>> config["defaults"]["transfers"]
        64
        >>> config["profiles"]["photos"]["remote"]
        'dropbox:photos'
    """
    # Find config file
    config_path = find_config_file(package_dir)

    # No config found - return empty structure
    if config_path is None:
        return {"defaults": {}, "profiles": {}, "rclone": {}}

    # Parse and return config
    return parse_toml(config_path)

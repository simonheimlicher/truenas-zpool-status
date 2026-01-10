"""
Main entry point for cloud-mirror.

This module provides:
- main(): Entry point for the cloud-mirror CLI with auto-direction detection
"""

from __future__ import annotations

import sys


def main(args: list[str] | None = None) -> int:
    """Main entry point for cloud-mirror CLI.

    Auto-detects direction (mirror-to-cloud or mirror-from-cloud) based on
    argument format and dispatches to appropriate handler.

    Supports profile-based configuration from cloud-mirror.toml:
    - Load config when --profile provided
    - Merge defaults → profile → CLI args (CLI always wins)
    - Validate source/destination after merge
    - Detect direction after merge (profile can provide source/dest)

    Args:
        args: Command-line arguments (uses sys.argv if None).

    Returns:
        Exit code: 0 for success, non-zero for failure.
    """
    from pathlib import Path

    from cloud_mirror.cli import parse_args
    from cloud_mirror.config import ConfigError, load_config, merge_config
    from cloud_mirror.direction import DirectionError, SyncDirection, detect_direction

    parsed = parse_args(args)

    # Load config if --profile provided
    config_data: dict[str, dict[str, object]] = {}
    profile: dict[str, object] | None = None

    if parsed.profile:
        package_dir = Path(__file__).parent
        try:
            config_data = load_config(package_dir)
        except ConfigError as e:
            print(f"Error loading config: {e}", file=sys.stderr)  # noqa: T201
            return 1

        # Extract and validate profile
        if parsed.profile not in config_data.get("profiles", {}):
            available = ", ".join(config_data.get("profiles", {}).keys())
            msg = f"Error: Profile '{parsed.profile}' not found in config"
            if available:
                msg += f". Available profiles: {available}"
            print(msg, file=sys.stderr)  # noqa: T201
            return 1

        profile_data = config_data["profiles"][parsed.profile]
        profile = profile_data if isinstance(profile_data, dict) else None

    # Build CLI args dict (only non-None values for positionals)
    cli_args: dict[str, object] = {}
    if parsed.source is not None:
        cli_args["source"] = parsed.source
    if parsed.destination is not None:
        cli_args["destination"] = parsed.destination
    cli_args["transfers"] = parsed.transfers
    cli_args["tpslimit"] = parsed.tpslimit
    cli_args["dry_run"] = parsed.dry_run
    cli_args["keep_versions"] = parsed.keep_versions
    cli_args["keep_snapshot"] = parsed.keep_snapshot
    cli_args["keep_clone"] = parsed.keep_clone
    cli_args["keep_pre_snapshot"] = parsed.keep_pre_snapshot
    cli_args["no_pre_snapshot"] = parsed.no_pre_snapshot
    if parsed.config is not None:
        cli_args["config"] = parsed.config
    cli_args["verbose"] = parsed.verbose

    # Merge config: defaults → profile → CLI args
    defaults = config_data.get("defaults", {})
    merged = merge_config(defaults, profile, cli_args)

    # Extract source/destination from merged config
    source = merged.get("source")
    destination = merged.get("destination")

    if not source or not destination:
        print(
            "Error: Both source and destination are required.\n"
            "Provide them as positional arguments or via profile settings.",
            file=sys.stderr,  # noqa: T201
        )
        return 1

    # Auto-detect direction from source and destination (AFTER merge)
    try:
        endpoints = detect_direction(source, destination)
    except DirectionError as e:
        print(f"Error: {e}", file=sys.stderr)  # noqa: T201
        return 1

    # Convert config_path to Path if string
    config_path = merged.get("config")
    if isinstance(config_path, str):
        config_path = Path(config_path)

    if endpoints.direction == SyncDirection.PUSH:
        from cloud_mirror.push import run_push

        return run_push(
            dataset=endpoints.zfs_dataset,
            destination=endpoints.remote,
            config_path=config_path,
            transfers=merged.get("transfers", 64),
            tpslimit=merged.get("tpslimit", 12),
            dry_run=merged.get("dry_run", False),
            keep_versions=merged.get("keep_versions", 0),
            keep_snapshot=merged.get("keep_snapshot", False),
            keep_clone=merged.get("keep_clone", False),
            verbose=merged.get("verbose", 0),
        )
    else:
        from cloud_mirror.pull import run_pull

        return run_pull(
            remote=endpoints.remote,
            dataset=endpoints.zfs_dataset,
            config_path=config_path,
            transfers=merged.get("transfers", 64),
            tpslimit=merged.get("tpslimit", 12),
            dry_run=merged.get("dry_run", False),
            keep_pre_snapshot=merged.get("keep_pre_snapshot", False),
            no_pre_snapshot=merged.get("no_pre_snapshot", False),
            verbose=merged.get("verbose", 0),
        )


if __name__ == "__main__":
    sys.exit(main())

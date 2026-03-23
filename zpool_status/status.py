"""Parse zpool status output and enrich with disk identification from smartctl."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass


@dataclass
class DiskInfo:
    model: str
    serial: str


def get_zpool_status(pool: str | None = None) -> str:
    """Run `zpool status` and return its output."""
    cmd = ["zpool", "status"]
    if pool:
        cmd.append(pool)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            result.stderr.strip() or f"zpool status failed (exit {result.returncode})"
        )
    return result.stdout


def get_disk_info(device: str) -> DiskInfo:
    """Query smartctl for disk model and serial number."""
    dev_path = device if device.startswith("/") else f"/dev/{device}"
    result = subprocess.run(
        ["smartctl", "-i", dev_path],
        capture_output=True,
        text=True,
    )
    model = ""
    serial = ""
    for line in result.stdout.splitlines():
        # SATA: "Device Model:", NVMe: "Model Number:"
        if line.startswith("Device Model:") or line.startswith("Model Number:"):
            model = line.split(":", 1)[1].strip()
        elif line.startswith("Serial Number:") or line.startswith("Serial number:"):
            serial = line.split(":", 1)[1].strip()
    return DiskInfo(model=model, serial=serial)


# Patterns that are NOT physical devices in zpool status config section
_VDEV_TYPES = re.compile(
    r"^(mirror|raidz[123]?|spare|cache|log|special|dedup|replacing|spare)-?\d*$"
)


def is_physical_device(name: str) -> bool:
    """Check if a name in zpool status represents a physical device (not a vdev or pool)."""
    if _VDEV_TYPES.match(name):
        return False
    # Devices are typically sdX, nvmeXnYpZ, daX, or /dev/disk/by-id/... paths
    # They appear as leaf nodes under vdevs.
    # We detect them by exclusion: not a vdev type, and appears indented under config.
    return True


def _find_config_section(lines: list[str]) -> tuple[int, int]:
    """Find the start and end of the config section in zpool status output.

    Returns (header_line_index, end_index) where header_line is the NAME/STATE/... line.
    """
    config_start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("NAME") and "STATE" in line:
            config_start = i
            break
    if config_start == -1:
        return -1, -1

    # Config section ends at the next blank line or "errors:" line
    config_end = len(lines)
    for i in range(config_start + 1, len(lines)):
        stripped = lines[i].strip()
        if stripped == "" or stripped.startswith("errors:"):
            config_end = i
            break
    return config_start, config_end


def enrich_status(raw_output: str) -> str:
    """Add MODEL and SERIAL columns to zpool status output for physical devices."""
    lines = raw_output.splitlines()
    header_idx, config_end = _find_config_section(lines)
    if header_idx == -1:
        return raw_output

    header = lines[header_idx]
    # Parse column positions from the header
    # Typical: "\tNAME        STATE     READ WRITE CKSUM"
    cksum_end = header.rfind("CKSUM")
    if cksum_end == -1:
        return raw_output
    cksum_end += len("CKSUM")

    # Collect disk info for all physical devices first (batch to avoid repeated calls)
    device_lines: list[tuple[int, str]] = []  # (line_index, device_name)
    pool_name: str | None = None

    for i in range(header_idx + 1, config_end):
        parts = lines[i].split()
        if not parts:
            continue
        name = parts[0]
        # First non-empty line after header is the pool name
        if pool_name is None:
            pool_name = name
            continue
        if is_physical_device(name):
            device_lines.append((i, name))

    if not device_lines:
        return raw_output

    # Query smartctl for each device
    disk_infos: dict[int, DiskInfo] = {}
    for line_idx, dev_name in device_lines:
        disk_infos[line_idx] = get_disk_info(dev_name)

    # Determine column widths
    max_model = max((len(info.model) for info in disk_infos.values()), default=0)
    max_serial = max((len(info.serial) for info in disk_infos.values()), default=0)
    model_width = max(max_model, len("MODEL"))
    serial_width = max(max_serial, len("SERIAL"))

    # Build enriched output
    result_lines = []
    for i, line in enumerate(lines):
        if i == header_idx:
            # Extend header with new columns
            padded = line.ljust(cksum_end)
            result_lines.append(f"{padded}  {('MODEL').ljust(model_width)}  SERIAL")
        elif i in disk_infos:
            info = disk_infos[i]
            padded = line.ljust(cksum_end)
            result_lines.append(
                f"{padded}  {info.model.ljust(model_width)}  {info.serial}"
            )
        elif header_idx < i < config_end:
            # Pool/vdev lines — pad to align but no disk info
            padded = line.ljust(cksum_end)
            result_lines.append(padded)
        else:
            result_lines.append(line)
    return "\n".join(result_lines) + "\n"

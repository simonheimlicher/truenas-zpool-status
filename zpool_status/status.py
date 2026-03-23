"""Parse zpool status output and enrich with disk identification from smartctl."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass


@dataclass
class DiskInfo:
    model: str
    serial: str


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

# Patterns that are NOT physical devices in zpool status config section
_VDEV_TYPES = re.compile(
    r"^(mirror|raidz[123]?|spare|cache|log|special|dedup|replacing|spare)-?\d*$"
)


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


def resolve_device_path(name: str) -> str:
    """Resolve a device name to a path smartctl can query.

    Handles:
    - UUIDs: resolved via /dev/disk/by-partuuid/, then stripped to base device
    - Partition names (sdi3, nvme0n1p2): stripped to base device (sdi, nvme0n1)
    - Plain device names (sda): returned as /dev/sda
    """
    if _UUID_RE.match(name):
        partuuid_path = f"/dev/disk/by-partuuid/{name}"
        try:
            target = os.readlink(partuuid_path)
            # target is relative like "../../sda1", extract the device name
            partition = os.path.basename(target)
            return f"/dev/{_strip_partition(partition)}"
        except OSError:
            return f"/dev/disk/by-partuuid/{name}"

    if name.startswith("/"):
        return name

    return f"/dev/{_strip_partition(name)}"


def _strip_partition(name: str) -> str:
    """Strip partition suffix to get the base device.

    nvme0n1p2 -> nvme0n1  (NVMe: strip pN suffix)
    sdi3      -> sdi      (SATA/SCSI: strip trailing digits)
    sda       -> sda      (no partition, unchanged)
    """
    # NVMe: /dev/nvme0n1p2 -> /dev/nvme0n1
    nvme_match = re.match(r"^(nvme\d+n\d+)p\d+$", name)
    if nvme_match:
        return nvme_match.group(1)
    # SATA/SCSI: /dev/sdi3 -> /dev/sdi
    sata_match = re.match(r"^(sd[a-z]+)\d+$", name)
    if sata_match:
        return sata_match.group(1)
    return name


def get_disk_info(device: str) -> DiskInfo:
    """Query smartctl for disk model and serial number."""
    dev_path = resolve_device_path(device)
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


def is_physical_device(name: str) -> bool:
    """Check if a name in zpool status represents a physical device (not a vdev or pool)."""
    if _VDEV_TYPES.match(name):
        return False
    return True


def _find_config_sections(lines: list[str]) -> list[tuple[int, int]]:
    """Find all config sections in zpool status output.

    Returns list of (header_line_index, end_index) tuples.
    """
    sections = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("NAME") and "STATE" in lines[i]:
            header_idx = i
            # Config section ends at blank line or "errors:" line
            end_idx = len(lines)
            for j in range(header_idx + 1, len(lines)):
                stripped = lines[j].strip()
                if stripped == "" or stripped.startswith("errors:"):
                    end_idx = j
                    break
            sections.append((header_idx, end_idx))
            i = end_idx
        else:
            i += 1
    return sections


def enrich_status(raw_output: str) -> str:
    """Add MODEL and SERIAL columns to zpool status output for physical devices."""
    lines = raw_output.splitlines()
    sections = _find_config_sections(lines)
    if not sections:
        return raw_output

    # First pass: collect all physical devices across all sections
    # Maps line_index -> device_name
    all_device_lines: dict[int, str] = {}
    pool_lines: set[int] = set()  # lines that are pool names (first line after header)
    section_ranges: set[int] = set()  # all line indices within any config section

    for header_idx, config_end in sections:
        pool_found = False
        for i in range(header_idx + 1, config_end):
            section_ranges.add(i)
            parts = lines[i].split()
            if not parts:
                continue
            name = parts[0]
            if not pool_found:
                pool_lines.add(i)
                pool_found = True
                continue
            if is_physical_device(name):
                all_device_lines[i] = name

    if not all_device_lines:
        return raw_output

    # Query smartctl for each unique base device (avoid duplicate queries)
    disk_infos: dict[int, DiskInfo] = {}
    cache: dict[str, DiskInfo] = {}
    for line_idx, dev_name in all_device_lines.items():
        dev_path = resolve_device_path(dev_name)
        if dev_path not in cache:
            cache[dev_path] = get_disk_info(dev_name)
        disk_infos[line_idx] = cache[dev_path]

    # Determine column widths across ALL pools for consistent alignment
    max_model = max((len(info.model) for info in disk_infos.values()), default=0)
    max_serial = max((len(info.serial) for info in disk_infos.values()), default=0)
    model_width = max(max_model, len("MODEL"))
    serial_width = max(max_serial, len("SERIAL"))

    # Track which lines are headers
    header_indices = {h for h, _ in sections}

    # Build enriched output
    result_lines = []
    for i, line in enumerate(lines):
        if i in header_indices:
            cksum_end = line.rfind("CKSUM")
            if cksum_end == -1:
                result_lines.append(line)
                continue
            cksum_end += len("CKSUM")
            padded = line.ljust(cksum_end)
            result_lines.append(f"{padded}  {'MODEL'.ljust(model_width)}  SERIAL")
        elif i in disk_infos:
            cksum_end = _cksum_end_for_line(i, sections, lines)
            info = disk_infos[i]
            # Separate the fixed columns from any trailing text (e.g. "too many errors")
            fixed_part = line[:cksum_end].ljust(cksum_end)
            trailing = line[cksum_end:].strip()
            enriched = f"{fixed_part}  {info.model.ljust(model_width)}  {info.serial.ljust(serial_width)}"
            if trailing:
                enriched = f"{enriched}  {trailing}"
            result_lines.append(enriched)
        elif i in section_ranges:
            cksum_end = _cksum_end_for_line(i, sections, lines)
            padded = line[:cksum_end].ljust(cksum_end)
            result_lines.append(padded)
        else:
            result_lines.append(line)
    return "\n".join(result_lines) + "\n"


def _cksum_end_for_line(
    line_idx: int, sections: list[tuple[int, int]], lines: list[str]
) -> int:
    """Find the CKSUM column end position for the section containing line_idx."""
    for header_idx, config_end in sections:
        if header_idx < line_idx < config_end:
            pos = lines[header_idx].rfind("CKSUM")
            if pos != -1:
                return pos + len("CKSUM")
    return 0

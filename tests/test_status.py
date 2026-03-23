"""Tests for zpool status parsing and enrichment."""

from __future__ import annotations

from unittest.mock import patch

from zpool_status.status import (
    DiskInfo,
    enrich_status,
    get_disk_info,
    is_physical_device,
)

SAMPLE_ZPOOL_STATUS = """\
  pool: tank
 state: ONLINE
  scan: scrub repaired 0B in 00:01:23 with 0 errors on Sun Mar 22 00:24:01 2026
config:

\tNAME        STATE     READ WRITE CKSUM
\ttank        ONLINE       0     0     0
\t  mirror-0  ONLINE       0     0     0
\t    sda     ONLINE       0     0     0
\t    sdb     ONLINE       0     0     0
\t  mirror-1  ONLINE       0     0     0
\t    sdc     ONLINE       0     0     0
\t    sdd     ONLINE       0     0     0

errors: No known data errors
"""

SAMPLE_SMARTCTL_SDA = """\
smartctl 7.2 2020-12-30 r5155 [x86_64-linux-5.15.0] (local build)
Copyright (C) 2002-20, Bruce Allen, Christian Franke, www.smartmontools.org

=== START OF INFORMATION SECTION ===
Device Model:     WDC WD40EFRX-68N32N0
Serial Number:    WD-WCC7K0AAA111
Firmware Version: 82.00A82
User Capacity:    4,000,787,030,016 bytes [4.00 TB]
"""

SAMPLE_SMARTCTL_SDB = """\
smartctl 7.2 2020-12-30 r5155 [x86_64-linux-5.15.0] (local build)
Copyright (C) 2002-20, Bruce Allen, Christian Franke, www.smartmontools.org

=== START OF INFORMATION SECTION ===
Device Model:     WDC WD40EFRX-68N32N0
Serial Number:    WD-WCC7K0BBB222
Firmware Version: 82.00A82
"""

SAMPLE_SMARTCTL_SDC = """\
smartctl 7.2 2020-12-30 r5155 [x86_64-linux-5.15.0] (local build)

=== START OF INFORMATION SECTION ===
Model Number:     Samsung SSD 970 EVO Plus 1TB
Serial Number:    S4EWNX0NCCC333
"""

SAMPLE_SMARTCTL_SDD = """\
smartctl 7.2 2020-12-30 r5155 [x86_64-linux-5.15.0] (local build)

=== START OF INFORMATION SECTION ===
Model Number:     Samsung SSD 970 EVO Plus 1TB
Serial Number:    S4EWNX0NDDD444
"""


class TestIsPhysicalDevice:
    def test_sd_devices(self) -> None:
        assert is_physical_device("sda")
        assert is_physical_device("sdb1")

    def test_nvme_devices(self) -> None:
        assert is_physical_device("nvme0n1")
        assert is_physical_device("nvme0n1p1")

    def test_mirror_vdev(self) -> None:
        assert not is_physical_device("mirror-0")
        assert not is_physical_device("mirror-1")

    def test_raidz_vdev(self) -> None:
        assert not is_physical_device("raidz1-0")
        assert not is_physical_device("raidz2-1")
        assert not is_physical_device("raidz3-0")

    def test_special_vdevs(self) -> None:
        assert not is_physical_device("spare-0")
        assert not is_physical_device("cache-0")
        assert not is_physical_device("log-0")

    def test_replacing_vdev(self) -> None:
        assert not is_physical_device("replacing-0")


class TestGetDiskInfo:
    def test_sata_device(self) -> None:
        with patch("zpool_status.status.subprocess.run") as mock_run:
            mock_run.return_value.stdout = SAMPLE_SMARTCTL_SDA
            mock_run.return_value.returncode = 0
            info = get_disk_info("sda")
        assert info.model == "WDC WD40EFRX-68N32N0"
        assert info.serial == "WD-WCC7K0AAA111"
        mock_run.assert_called_once_with(
            ["smartctl", "-i", "/dev/sda"],
            capture_output=True,
            text=True,
        )

    def test_nvme_device(self) -> None:
        with patch("zpool_status.status.subprocess.run") as mock_run:
            mock_run.return_value.stdout = SAMPLE_SMARTCTL_SDC
            mock_run.return_value.returncode = 0
            info = get_disk_info("nvme0n1")
        assert info.model == "Samsung SSD 970 EVO Plus 1TB"
        assert info.serial == "S4EWNX0NCCC333"

    def test_absolute_path(self) -> None:
        with patch("zpool_status.status.subprocess.run") as mock_run:
            mock_run.return_value.stdout = SAMPLE_SMARTCTL_SDA
            mock_run.return_value.returncode = 0
            get_disk_info("/dev/disk/by-id/some-disk")
        mock_run.assert_called_once_with(
            ["smartctl", "-i", "/dev/disk/by-id/some-disk"],
            capture_output=True,
            text=True,
        )

    def test_smartctl_failure_returns_empty(self) -> None:
        with patch("zpool_status.status.subprocess.run") as mock_run:
            mock_run.return_value.stdout = ""
            mock_run.return_value.returncode = 1
            info = get_disk_info("sda")
        assert info.model == ""
        assert info.serial == ""


SMARTCTL_OUTPUTS = {
    "/dev/sda": SAMPLE_SMARTCTL_SDA,
    "/dev/sdb": SAMPLE_SMARTCTL_SDB,
    "/dev/sdc": SAMPLE_SMARTCTL_SDC,
    "/dev/sdd": SAMPLE_SMARTCTL_SDD,
}


def _mock_smartctl(cmd: list[str], **kwargs: object) -> object:
    """Mock subprocess.run that returns smartctl output based on device path."""
    dev = cmd[-1]

    class Result:
        stdout = SMARTCTL_OUTPUTS.get(dev, "")
        stderr = ""
        returncode = 0

    return Result()


class TestEnrichStatus:
    def test_adds_model_and_serial_columns(self) -> None:
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(SAMPLE_ZPOOL_STATUS)

        lines = result.splitlines()
        # Find the header line
        header = next(l for l in lines if "NAME" in l and "STATE" in l)
        assert "MODEL" in header
        assert "SERIAL" in header

    def test_physical_devices_have_info(self) -> None:
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(SAMPLE_ZPOOL_STATUS)

        assert "WD-WCC7K0AAA111" in result
        assert "WD-WCC7K0BBB222" in result
        assert "S4EWNX0NCCC333" in result
        assert "S4EWNX0NDDD444" in result
        assert "WDC WD40EFRX-68N32N0" in result
        assert "Samsung SSD 970 EVO Plus 1TB" in result

    def test_vdev_lines_have_no_disk_info(self) -> None:
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(SAMPLE_ZPOOL_STATUS)

        for line in result.splitlines():
            if "mirror-0" in line or "mirror-1" in line:
                assert "WDC" not in line
                assert "Samsung" not in line

    def test_non_config_lines_unchanged(self) -> None:
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(SAMPLE_ZPOOL_STATUS)

        assert "pool: tank" in result
        assert "state: ONLINE" in result
        assert "errors: No known data errors" in result

    def test_no_config_section_returns_raw(self) -> None:
        raw = "some random output with no config\n"
        result = enrich_status(raw)
        assert result == raw

    def test_single_disk_pool(self) -> None:
        raw = """\
  pool: simple
 state: ONLINE
config:

\tNAME     STATE     READ WRITE CKSUM
\tsimple   ONLINE       0     0     0
\t  sda    ONLINE       0     0     0

errors: No known data errors
"""
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(raw)
        assert "WDC WD40EFRX-68N32N0" in result
        assert "WD-WCC7K0AAA111" in result

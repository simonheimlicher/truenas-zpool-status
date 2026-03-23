"""Tests for zpool status parsing and enrichment."""

from __future__ import annotations

from unittest.mock import patch

from zpool_status.status import (
    DiskInfo,
    _strip_partition,
    enrich_status,
    get_disk_info,
    is_physical_device,
    resolve_device_path,
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

SAMPLE_SMARTCTL_SDE = """\
smartctl 7.2 2020-12-30 r5155 [x86_64-linux-5.15.0] (local build)

=== START OF INFORMATION SECTION ===
Device Model:     Seagate IronWolf 8TB
Serial Number:    ZCT0EEE555
"""

SAMPLE_SMARTCTL_NVME = """\
smartctl 7.4 2023-08-01 r5530 [x86_64-linux-6.1.0] (local build)

=== START OF INFORMATION SECTION ===
Model Number:     Samsung SSD 980 PRO 500GB
Serial Number:    S5GXNF0NFFF666
"""


class TestStripPartition:
    def test_sata_with_partition(self) -> None:
        assert _strip_partition("sda1") == "sda"
        assert _strip_partition("sdi3") == "sdi"
        assert _strip_partition("sdj5") == "sdj"

    def test_sata_without_partition(self) -> None:
        assert _strip_partition("sda") == "sda"
        assert _strip_partition("sdz") == "sdz"

    def test_nvme_with_partition(self) -> None:
        assert _strip_partition("nvme0n1p1") == "nvme0n1"
        assert _strip_partition("nvme0n1p2") == "nvme0n1"
        assert _strip_partition("nvme1n1p3") == "nvme1n1"

    def test_nvme_without_partition(self) -> None:
        assert _strip_partition("nvme0n1") == "nvme0n1"


class TestResolveDevicePath:
    def test_plain_device(self) -> None:
        assert resolve_device_path("sda") == "/dev/sda"

    def test_partition_stripped(self) -> None:
        assert resolve_device_path("sdi3") == "/dev/sdi"
        assert resolve_device_path("nvme0n1p2") == "/dev/nvme0n1"

    def test_absolute_path_passthrough(self) -> None:
        assert resolve_device_path("/dev/disk/by-id/foo") == "/dev/disk/by-id/foo"

    def test_uuid_resolved_via_readlink(self) -> None:
        uuid = "23e0b0a2-b80e-43f9-afe7-2618efe4ef73"
        with patch("zpool_status.status.os.readlink", return_value="../../sdi5"):
            result = resolve_device_path(uuid)
        assert result == "/dev/sdi"

    def test_uuid_nvme_resolved(self) -> None:
        uuid = "3b6737ca-9da2-11ea-aa29-408d5cb328b3"
        with patch("zpool_status.status.os.readlink", return_value="../../nvme0n1p2"):
            result = resolve_device_path(uuid)
        assert result == "/dev/nvme0n1"

    def test_uuid_readlink_failure_falls_back(self) -> None:
        uuid = "deadbeef-dead-beef-dead-beefdeadbeef"
        with patch("zpool_status.status.os.readlink", side_effect=OSError):
            result = resolve_device_path(uuid)
        assert result == f"/dev/disk/by-partuuid/{uuid}"


class TestIsPhysicalDevice:
    def test_sd_devices(self) -> None:
        assert is_physical_device("sda")
        assert is_physical_device("sdb1")

    def test_nvme_devices(self) -> None:
        assert is_physical_device("nvme0n1")
        assert is_physical_device("nvme0n1p1")

    def test_uuid_devices(self) -> None:
        assert is_physical_device("23e0b0a2-b80e-43f9-afe7-2618efe4ef73")
        assert is_physical_device("3b6737ca-9da2-11ea-aa29-408d5cb328b3")

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

    def test_uuid_device(self) -> None:
        with patch("zpool_status.status.os.readlink", return_value="../../sda1"):
            with patch("zpool_status.status.subprocess.run") as mock_run:
                mock_run.return_value.stdout = SAMPLE_SMARTCTL_SDA
                mock_run.return_value.returncode = 0
                info = get_disk_info("23e0b0a2-b80e-43f9-afe7-2618efe4ef73")
        assert info.model == "WDC WD40EFRX-68N32N0"
        assert info.serial == "WD-WCC7K0AAA111"
        mock_run.assert_called_once_with(
            ["smartctl", "-i", "/dev/sda"],
            capture_output=True,
            text=True,
        )

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
    "/dev/sde": SAMPLE_SMARTCTL_SDE,
    "/dev/nvme0n1": SAMPLE_SMARTCTL_NVME,
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


MULTI_POOL_STATUS = """\
  pool: fast1
 state: ONLINE
config:

\tNAME        STATE     READ WRITE CKSUM
\tfast1       ONLINE       0     0     0
\t  mirror-0  ONLINE       0     0     0
\t    sda     ONLINE       0     0     0
\t    sdb     ONLINE       0     0     0

errors: No known data errors

  pool: large1
 state: ONLINE
config:

\tNAME        STATE     READ WRITE CKSUM
\tlarge1      ONLINE       0     0     0
\t  raidz2-0  ONLINE       0     0     0
\t    sdc     ONLINE       0     0     0
\t    sdd     ONLINE       0     0     0
\t    sde     ONLINE       0     0     0

errors: No known data errors
"""


class TestMultiPool:
    def test_all_pools_get_columns(self) -> None:
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(MULTI_POOL_STATUS)

        headers = [l for l in result.splitlines() if "NAME" in l and "STATE" in l]
        assert len(headers) == 2
        assert all("MODEL" in h and "SERIAL" in h for h in headers)

    def test_all_pools_have_disk_info(self) -> None:
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(MULTI_POOL_STATUS)

        # fast1 pool devices
        assert "WD-WCC7K0AAA111" in result
        assert "WD-WCC7K0BBB222" in result
        # large1 pool devices
        assert "S4EWNX0NCCC333" in result
        assert "S4EWNX0NDDD444" in result
        assert "ZCT0EEE555" in result

    def test_each_pool_errors_line_preserved(self) -> None:
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(MULTI_POOL_STATUS)

        assert result.count("errors: No known data errors") == 2


UUID_POOL_STATUS = """\
  pool: apps
 state: ONLINE
config:

\tNAME                                      STATE     READ WRITE CKSUM
\tapps                                      ONLINE       0     0     0
\t  mirror-0                                ONLINE       0     0     0
\t    23e0b0a2-b80e-43f9-afe7-2618efe4ef73  ONLINE       0     0     0
\t    4c4d2fb0-ff22-4709-b38c-1360e63b8c68  ONLINE       0     0     0

errors: No known data errors
"""


class TestUuidDevices:
    def _mock_readlink(self, path: str) -> str:
        mapping = {
            "/dev/disk/by-partuuid/23e0b0a2-b80e-43f9-afe7-2618efe4ef73": "../../sda1",
            "/dev/disk/by-partuuid/4c4d2fb0-ff22-4709-b38c-1360e63b8c68": "../../sdb1",
        }
        result = mapping.get(path)
        if result is None:
            raise OSError(f"No such file: {path}")
        return result

    def test_uuid_devices_resolved_and_enriched(self) -> None:
        with (
            patch("zpool_status.status.os.readlink", side_effect=self._mock_readlink),
            patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl),
        ):
            result = enrich_status(UUID_POOL_STATUS)

        assert "MODEL" in result
        assert "SERIAL" in result
        assert "WDC WD40EFRX-68N32N0" in result
        assert "WD-WCC7K0AAA111" in result
        assert "WD-WCC7K0BBB222" in result

    def test_uuid_devices_same_base_device_cached(self) -> None:
        """Two UUIDs resolving to the same base device should only call smartctl once."""
        single_disk_smartctl = {
            "/dev/sdi": SAMPLE_SMARTCTL_SDA,
        }

        def mock_readlink(path: str) -> str:
            # Both UUIDs map to different partitions on same disk
            mapping = {
                "/dev/disk/by-partuuid/23e0b0a2-b80e-43f9-afe7-2618efe4ef73": "../../sdi4",
                "/dev/disk/by-partuuid/4c4d2fb0-ff22-4709-b38c-1360e63b8c68": "../../sdi5",
            }
            result = mapping.get(path)
            if result is None:
                raise OSError(f"No such file: {path}")
            return result

        call_count = 0

        def mock_smartctl(cmd: list[str], **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            dev = cmd[-1]

            class Result:
                stdout = single_disk_smartctl.get(dev, "")
                stderr = ""
                returncode = 0

            return Result()

        with (
            patch("zpool_status.status.os.readlink", side_effect=mock_readlink),
            patch("zpool_status.status.subprocess.run", side_effect=mock_smartctl),
        ):
            enrich_status(UUID_POOL_STATUS)

        # Two UUIDs but same base device /dev/sdi — only one smartctl call
        assert call_count == 1


FAULTED_POOL_STATUS = """\
  pool: large1
 state: ONLINE
config:

\tNAME        STATE     READ WRITE CKSUM
\tlarge1      ONLINE       0     0     0
\t  raidz2-0  ONLINE       0     0     0
\t    sda     ONLINE       0     0     0
\t    sdb     ONLINE       0     0     0
\t    sdc     FAULTED     12   125     0  too many errors

errors: No known data errors
"""


class TestFaultedDevice:
    def test_trailing_text_after_model_serial(self) -> None:
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(FAULTED_POOL_STATUS)

        faulted_line = next(l for l in result.splitlines() if "FAULTED" in l)
        # MODEL and SERIAL should appear before "too many errors"
        model_pos = faulted_line.index("Samsung SSD 970 EVO Plus 1TB")
        serial_pos = faulted_line.index("S4EWNX0NCCC333")
        errors_pos = faulted_line.index("too many errors")
        assert model_pos < serial_pos < errors_pos

    def test_healthy_devices_unaffected(self) -> None:
        with patch("zpool_status.status.subprocess.run", side_effect=_mock_smartctl):
            result = enrich_status(FAULTED_POOL_STATUS)

        sda_line = next(l for l in result.splitlines() if "sda" in l)
        assert "WDC WD40EFRX-68N32N0" in sda_line
        assert "too many errors" not in sda_line

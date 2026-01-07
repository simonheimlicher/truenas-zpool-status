# Capability: Dropbox Mirror Pull

## Success Metric

**Quantitative Target:**

- **Baseline**: No way to pull from Dropbox to ZFS; manual download and copy required
- **Target**: `cloud-mirror.py remote dataset` pulls files with pre-pull snapshot for rollback safety
- **Measurement**: Pull integration tests pass; files sync from remote to local ZFS dataset

## Capability Integration Tests

### EI1: Full pull workflow syncs files from remote

```gherkin
GIVEN rclone remote testremote:source with files:
  | path              | content         |
  | file1.txt         | content of file1 |
  | subdir/file2.txt  | content of file2 |
AND empty ZFS dataset testpool/target
WHEN cloud-mirror.py testremote:source testpool/target executed
THEN files appear in /testpool/target/
AND pre-pull snapshot testpool/target@dropboxpull-pre-TIMESTAMP is created
AND pre-pull snapshot is destroyed after successful sync
```

### EI2: Pre-pull snapshot enables rollback on failure

```gherkin
GIVEN pull operation fails mid-sync (e.g., remote unreachable)
WHEN error is caught
THEN pre-pull snapshot is preserved (not destroyed)
AND error message includes rollback command:
  "zfs rollback testpool/target@dropboxpull-pre-TIMESTAMP"
```

### EI3: Direction auto-detected from argument order

```gherkin
GIVEN cloud-mirror.py script
WHEN executed with: cloud-mirror.py testremote:source testpool/target
THEN direction detected as PULL (remote first)
WHEN executed with: cloud-mirror.py testpool/source testremote:target
THEN direction detected as PUSH (dataset first)
```

### EI4: Symlinks restored from .rclonelink files

```gherkin
GIVEN remote has:
  | path                | content    |
  | target.txt          | (content)  |
  | link.txt.rclonelink | target.txt |
WHEN pull executed with --links
THEN local dataset has:
  | path       | type    | target     |
  | target.txt | file    | -          |
  | link.txt   | symlink | target.txt |
```

## System Integration

This capability extends `cloud-mirror.py` to support bidirectional sync. It depends on:

- Capability-10 (Docker Test Environment) for running ZFS integration tests
- Capability-27 (Dropbox Push) for shared infrastructure (validation, rclone, CLI framework)

Pull is designed for Use Case 1: mirroring a flat Dropbox folder to a local ZFS dataset for apps like Calibre and Audiobookshelf.

Future work (Use Cases 2 and 3) will add nested dataset support for restoring pushed backups.

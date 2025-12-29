# AGENTS.md

This file provides guidance to AI Coding agents such as [Claude Code](https://claude.ai/code) and [OpenAI Codex](https://openai.com/codex) when working with code in this repository.

## Project Overview

A Python script that creates recursive ZFS snapshots, clones the dataset tree to ensure consistent traversal of nested datasets, pushes to Dropbox via rclone, and cleans up. Designed for TrueNAS SCALE where the built-in Cloud Sync Tasks fail on datasets with nested child datasets.

## Requirements

- TrueNAS SCALE 25.10.1+ (Python 3.11+, rclone pre-installed)
- rclone configured with Dropbox

## Running the Script

```bash
# Basic sync
python3 dropbox-push.py apps/config dropbox:TrueNAS-Backup/apps-config \
    --rclone-config /mnt/system/admin/dropbox-push/rclone.conf

# Dry run with verbose output
python3 dropbox-push.py apps/config dropbox:TrueNAS-Backup/apps-config \
    --rclone-config /mnt/system/admin/dropbox-push/rclone.conf --dry-run -v

# Debug mode
python3 dropbox-push.py apps/config dropbox:TrueNAS-Backup/apps-config \
    --rclone-config /mnt/system/admin/dropbox-push/rclone.conf --debug --keep-clone
```

## Key Concepts

- **Clone tree approach**: Rather than traversing `.zfs/snapshot/` (which still shows live child dataset mountpoints), the script creates clones from the recursive snapshot, providing a truly immutable, consistent view
- **Lock file**: Uses file-based locking (`/run/dropbox-push.{dataset}.lock`) to prevent concurrent runs
- **Version retention**: `--keep-versions N` moves changed/deleted files to `.versions/<timestamp>/` on the remote before sync

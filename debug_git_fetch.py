#!/usr/bin/env python3
"""Debug script to understand why git fetch fails in test."""

import subprocess
import tempfile
from pathlib import Path

# Create temp directory
with tempfile.TemporaryDirectory() as tmp:
    tmp_path = Path(tmp)

    # Create remote repo
    remote_path = tmp_path / "remote" / "repo"
    remote_path.mkdir(parents=True)

    print("Creating remote repo...")
    subprocess.run(
        ["git", "init", "-b", "main", str(remote_path)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(remote_path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(remote_path), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )

    # Create initial commit in remote
    (remote_path / "file.txt").write_text("initial")
    subprocess.run(
        ["git", "-C", str(remote_path), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(remote_path), "commit", "-m", "Initial"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(remote_path), "tag", "-a", "v0.1.0", "-m", "v0.1.0"],
        check=True,
        capture_output=True,
    )

    remote_commit = subprocess.run(
        ["git", "-C", str(remote_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    print(f"Remote commit: {remote_commit}")

    # Create local repo
    local_path = tmp_path / "local" / "repo"
    local_path.mkdir(parents=True)

    print("\nCreating local repo...")
    subprocess.run(
        ["git", "init", "-b", "main", str(local_path)], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(local_path), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(local_path), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )

    # Create initial commit in local (different from remote!)
    (local_path / "file.txt").write_text("initial")
    subprocess.run(
        ["git", "-C", str(local_path), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(local_path), "commit", "-m", "Initial"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(local_path), "tag", "-a", "v0.1.0", "-m", "v0.1.0"],
        check=True,
        capture_output=True,
    )

    local_commit = subprocess.run(
        ["git", "-C", str(local_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    print(f"Local commit: {local_commit}")
    print(f"Commits match: {local_commit == remote_commit}")

    # Add remote
    print(f"\nAdding remote: {remote_path}")
    subprocess.run(
        ["git", "-C", str(local_path), "remote", "add", "origin", str(remote_path)],
        check=True,
        capture_output=True,
    )

    # Try to fetch
    print("\nAttempting fetch...")
    result = subprocess.run(
        ["git", "-C", str(local_path), "fetch", "origin", "main", "--tags", "--quiet"],
        capture_output=True,
        text=True,
    )

    print(f"Return code: {result.returncode}")
    print(f"Stdout: {result.stdout}")
    print(f"Stderr: {result.stderr}")

    if result.returncode == 0:
        print("\nFetch succeeded! Now try describe...")
        describe_result = subprocess.run(
            [
                "git",
                "-C",
                str(local_path),
                "describe",
                "--tags",
                "--always",
                "origin/main",
            ],
            capture_output=True,
            text=True,
        )
        print(f"Describe return code: {describe_result.returncode}")
        print(f"Describe stdout: {describe_result.stdout}")
        print(f"Describe stderr: {describe_result.stderr}")
    else:
        print("\nFetch failed!")

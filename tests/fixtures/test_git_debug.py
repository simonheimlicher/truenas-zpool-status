"""Debug test to understand commit creation."""

from pathlib import Path

from tests.fixtures.git_fixtures import with_git_repo


def test_debug_commits(tmp_path: Path) -> None:
    """Debug: Check what commits are created."""
    with with_git_repo(tmp_path, commits=["Initial"]) as repo:
        # Show all commits
        result = repo.run_git("log", "--oneline", "--all")
        print("\n=== Git log ===")
        print(result.stdout)

        initial_commit = repo.current_commit()
        print(f"\nCurrent commit: {initial_commit}")

        # Create tag
        repo.create_tag("v0.1.0")

        # Show what the tag points to
        tag_commit = repo.get_commit("v0.1.0")
        print(f"Tag v0.1.0 points to: {tag_commit}")

        # Show log again
        result = repo.run_git("log", "--oneline", "--all", "--decorate")
        print("\n=== Git log after tag ===")
        print(result.stdout)

        assert tag_commit == initial_commit, f"Tag {tag_commit} != current {initial_commit}"

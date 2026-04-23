from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChangeSet:
    """A set of code changes detected by git.

    Attributes
    ----------
    summary : str
        Human-readable label for what was compared.
    changed_files : list[str]
        Paths of files that changed.
    diffs : dict[str, str]
        Mapping of filepath to unified diff text.
    """

    summary: str
    changed_files: list[str]
    diffs: dict[str, str]


class GitClient:
    """Thin wrapper around local git commands.

    Parameters
    ----------
    repo_dir : str | Path | None
        Path to the git repository. Defaults to current directory.
    """

    def __init__(self, repo_dir: str | Path | None = None) -> None:
        self._cwd = str(repo_dir) if repo_dir else None
        self._verify_git()

    # MARK: Public Methods

    def get_last_commits(self, n: int = 1) -> ChangeSet:
        """Diff the last *n* commits against the state before them.

        Parameters
        ----------
        n : int
            Number of commits to include.

        Returns
        -------
        ChangeSet
            Combined changes across the last *n* commits.
        """
        ref = f"HEAD~{n}" if n > 0 else "HEAD"
        summary_lines = self._run("log", "--oneline", f"-{n}", "HEAD").strip()
        return self._diff_range(ref, "HEAD", summary=f"Last {n} commit(s):\n{summary_lines}")

    def get_commit(self, commit_hash: str) -> ChangeSet:
        """Diff a single commit against its parent.

        Parameters
        ----------
        commit_hash : str
            Full or short commit hash.

        Returns
        -------
        ChangeSet
            Changes introduced by the commit.
        """
        message = self._run("log", "--format=%s", "-1", commit_hash).strip()
        return self._diff_range(
            f"{commit_hash}~1", commit_hash,
            summary=f"{commit_hash[:10]}: {message}",
        )

    def get_uncommitted(self) -> ChangeSet:
        """Diff working tree and staged changes against HEAD.

        Returns
        -------
        ChangeSet
            Uncommitted changes (staged + unstaged).
        """
        raw_diff = self._run("diff", "HEAD")
        if not raw_diff.strip():
            return ChangeSet(summary="No uncommitted changes", changed_files=[], diffs={})

        changed = self._run("diff", "--name-only", "HEAD").strip().splitlines()
        diffs = self._split_diff(raw_diff)
        return ChangeSet(
            summary=f"Uncommitted changes ({len(changed)} file(s))",
            changed_files=changed,
            diffs=diffs,
        )

    def get_branch_diff(self, base: str = "main") -> ChangeSet:
        """Diff current branch against a base branch.

        Parameters
        ----------
        base : str
            Base branch to compare against.

        Returns
        -------
        ChangeSet
            All changes on the current branch since it diverged from *base*.
        """
        merge_base = self._run("merge-base", base, "HEAD").strip()
        count = self._run("rev-list", "--count", f"{merge_base}..HEAD").strip()
        return self._diff_range(
            merge_base, "HEAD",
            summary=f"{count} commit(s) ahead of {base}",
        )

    # MARK: Helpers

    def _run(self, *args: str) -> str:
        """Execute a git command and return stdout."""
        result = subprocess.run(
            ["git", *args],
            cwd=self._cwd,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def _verify_git(self) -> None:
        """Verify we're inside a git repository."""
        try:
            self._run("rev-parse", "--git-dir")
        except RuntimeError:
            raise RuntimeError(f"Not a git repository: {self._cwd or '.'}")

    def _diff_range(self, from_ref: str, to_ref: str, *, summary: str) -> ChangeSet:
        """Compute a ChangeSet between two git refs."""
        raw_diff = self._run("diff", from_ref, to_ref)
        changed = self._run("diff", "--name-only", from_ref, to_ref).strip().splitlines()
        changed = [f for f in changed if f]
        diffs = self._split_diff(raw_diff)
        return ChangeSet(summary=summary, changed_files=changed, diffs=diffs)

    @staticmethod
    def _split_diff(raw_diff: str) -> dict[str, str]:
        """Split a unified diff into per-file chunks keyed by filepath."""
        chunks: dict[str, str] = {}
        current_file: str | None = None
        current_lines: list[str] = []

        for line in raw_diff.splitlines(keepends=True):
            if line.startswith("diff --git"):
                if current_file and current_lines:
                    chunks[current_file] = "".join(current_lines)
                parts = line.strip().split(" b/", 1)
                current_file = parts[1] if len(parts) == 2 else None
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_file and current_lines:
            chunks[current_file] = "".join(current_lines)
        return chunks

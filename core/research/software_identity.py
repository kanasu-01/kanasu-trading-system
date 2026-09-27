"""Executable software identity boundary for research evidence."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Protocol


GitCommandResult = subprocess.CompletedProcess[str]
GitCommandRunner = Callable[
    [tuple[str, ...], Path],
    GitCommandResult,
]


@dataclass(frozen=True)
class SoftwareIdentity:
    """Exact executable repository identity when it can be established."""

    repository_revision: str | None
    worktree_clean: bool | None

    def __post_init__(self) -> None:
        if self.repository_revision is not None:
            if (
                not isinstance(self.repository_revision, str)
                or not self.repository_revision.strip()
            ):
                raise ValueError(
                    "repository_revision must be a non-empty "
                    "string or None"
                )

        if (
            self.worktree_clean is not None
            and type(self.worktree_clean) is not bool
        ):
            raise TypeError(
                "worktree_clean must be a bool or None"
            )

    @property
    def is_exact(self) -> bool:
        """Return whether revision and clean executable state are exact."""

        return (
            self.repository_revision is not None
            and self.worktree_clean is True
        )


class SoftwareIdentityProvider(Protocol):
    """Composition boundary for executable software identity."""

    def resolve(self) -> SoftwareIdentity:
        ...


def _run_git_command(
    args: tuple[str, ...],
    repository_root: Path,
) -> GitCommandResult:
    return subprocess.run(
        ["git", *args],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


class GitSoftwareIdentityProvider:
    """Resolve repository revision and executable worktree cleanliness."""

    def __init__(
        self,
        repository_root: str | Path = ".",
        *,
        git_runner: GitCommandRunner | None = None,
    ):
        self.repository_root = Path(repository_root)
        self._git_runner = git_runner or _run_git_command

    def _try_git(
        self,
        args: tuple[str, ...],
    ) -> GitCommandResult | None:
        try:
            return self._git_runner(
                args,
                self.repository_root,
            )
        except (OSError, subprocess.SubprocessError):
            return None

    def resolve(self) -> SoftwareIdentity:
        revision_result = self._try_git(
            ("rev-parse", "--verify", "HEAD")
        )

        if (
            revision_result is None
            or revision_result.returncode != 0
        ):
            return SoftwareIdentity(
                repository_revision=None,
                worktree_clean=None,
            )

        revision = (
            revision_result.stdout or ""
        ).strip()

        if not revision:
            return SoftwareIdentity(
                repository_revision=None,
                worktree_clean=None,
            )

        status_result = self._try_git(
            (
                "status",
                "--porcelain",
                "--untracked-files=normal",
            )
        )

        if (
            status_result is None
            or status_result.returncode != 0
        ):
            return SoftwareIdentity(
                repository_revision=revision,
                worktree_clean=None,
            )

        return SoftwareIdentity(
            repository_revision=revision,
            worktree_clean=not bool(
                (status_result.stdout or "").strip()
            ),
        )
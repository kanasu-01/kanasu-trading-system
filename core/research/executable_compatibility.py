"""Fail-closed executable compatibility proof for fixed historical candidates."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import subprocess


GitCommandResult = subprocess.CompletedProcess[str]
GitCommandRunner = Callable[[tuple[str, ...], Path], GitCommandResult]


class ExecutableCompatibilityOperationalError(RuntimeError):
    """Git infrastructure could not reliably establish executable compatibility."""


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


@dataclass(frozen=True)
class ExecutableCompatibilityResult:
    """Whether non-research executable core changed across revisions."""

    compatible: bool
    changed_paths: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if type(self.compatible) is not bool:
            raise TypeError("compatible must be a bool")
        if not isinstance(self.changed_paths, tuple):
            raise TypeError("changed_paths must be a tuple")
        if any(
            not isinstance(path, str) or not path
            for path in self.changed_paths
        ):
            raise ValueError("changed_paths must contain non-empty strings")
        if not isinstance(self.reason, str):
            raise TypeError("reason must be a string")


class GitHistoricalExecutableCompatibilityChecker:
    """
    Prove a fixed historical candidate did not silently change executable core.

    M9.6 itself is allowed to change only the research orchestration layer.
    Any Git-tracked change under ``core/`` outside ``core/research/`` between
    the historical ExperimentSpec revision and the current exact evaluator
    revision makes the fixed executable claim incompatible for this MVP gate.
    """

    def __init__(
        self,
        repository_root: str | Path = ".",
        *,
        git_runner: GitCommandRunner | None = None,
    ) -> None:
        self.repository_root = Path(repository_root)
        self._git_runner = git_runner or _run_git_command

    def _run_verified_git(
        self,
        args: tuple[str, ...],
    ) -> GitCommandResult:
        try:
            result = self._git_runner(
                args,
                self.repository_root,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ExecutableCompatibilityOperationalError(
                "Git executable-compatibility check could not run"
            ) from error

        if result.returncode != 0:
            message = (result.stderr or result.stdout or "").strip()
            if not message:
                message = "Git could not compare historical and current revisions"
            raise ExecutableCompatibilityOperationalError(
                message[:1000]
            )

        return result

    @staticmethod
    def _require_revision(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()

    def check(
        self,
        *,
        historical_revision: str,
        current_revision: str,
    ) -> ExecutableCompatibilityResult:
        historical_revision = self._require_revision(
            historical_revision,
            "historical_revision",
        )
        current_revision = self._require_revision(
            current_revision,
            "current_revision",
        )

        result = self._run_verified_git(
            (
                "diff",
                "--name-only",
                historical_revision,
                current_revision,
                "--",
                "core",
            )
        )

        changed_paths = tuple(
            line.strip().replace("\\", "/")
            for line in (result.stdout or "").splitlines()
            if line.strip()
        )

        executable_changes = tuple(
            path
            for path in changed_paths
            if not (
                path == "core/research"
                or path.startswith("core/research/")
            )
        )

        if executable_changes:
            return ExecutableCompatibilityResult(
                compatible=False,
                changed_paths=executable_changes,
                reason=(
                    "historical fixed candidate executable core changed "
                    "outside the research orchestration layer"
                ),
            )

        return ExecutableCompatibilityResult(
            compatible=True,
            changed_paths=(),
            reason="non-research executable core is unchanged",
        )

from pathlib import Path
import subprocess

import pytest

from core.research.software_identity import (
    GitSoftwareIdentityProvider,
    SoftwareIdentity,
)


REVISION = "d21c204da909f3e2c6201c8ca9e8af005074372f"


def result(
    returncode: int,
    stdout: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr="",
    )


def scripted_runner(*outcomes):
    pending = iter(outcomes)
    calls = []

    def run(args, repository_root):
        calls.append((args, repository_root))
        outcome = next(pending)

        if isinstance(outcome, BaseException):
            raise outcome

        return outcome

    return run, calls


def test_clean_repository_identity_is_exact():
    run, calls = scripted_runner(
        result(0, REVISION + "\n"),
        result(0, ""),
    )

    identity = GitSoftwareIdentityProvider(
        "repo",
        git_runner=run,
    ).resolve()

    assert identity == SoftwareIdentity(
        repository_revision=REVISION,
        worktree_clean=True,
    )
    assert identity.is_exact is True

    assert calls == [
        (
            ("rev-parse", "--verify", "HEAD"),
            Path("repo"),
        ),
        (
            (
                "status",
                "--porcelain",
                "--untracked-files=normal",
            ),
            Path("repo"),
        ),
    ]


def test_dirty_repository_identity_is_not_exact():
    run, _ = scripted_runner(
        result(0, REVISION),
        result(0, " M core/example.py\n?? new.py\n"),
    )

    identity = GitSoftwareIdentityProvider(
        git_runner=run
    ).resolve()

    assert identity.repository_revision == REVISION
    assert identity.worktree_clean is False
    assert identity.is_exact is False


def test_unknown_revision_does_not_query_worktree_status():
    run, calls = scripted_runner(
        result(128),
    )

    identity = GitSoftwareIdentityProvider(
        git_runner=run
    ).resolve()

    assert identity == SoftwareIdentity(
        repository_revision=None,
        worktree_clean=None,
    )
    assert identity.is_exact is False
    assert len(calls) == 1


def test_empty_revision_is_unknown():
    run, calls = scripted_runner(
        result(0, "\n"),
    )

    identity = GitSoftwareIdentityProvider(
        git_runner=run
    ).resolve()

    assert identity.repository_revision is None
    assert identity.worktree_clean is None
    assert identity.is_exact is False
    assert len(calls) == 1


def test_status_failure_preserves_revision_but_not_exact_identity():
    run, _ = scripted_runner(
        result(0, REVISION),
        result(128),
    )

    identity = GitSoftwareIdentityProvider(
        git_runner=run
    ).resolve()

    assert identity.repository_revision == REVISION
    assert identity.worktree_clean is None
    assert identity.is_exact is False


def test_unavailable_git_returns_unknown_identity():
    run, _ = scripted_runner(
        FileNotFoundError("git executable not found"),
    )

    identity = GitSoftwareIdentityProvider(
        git_runner=run
    ).resolve()

    assert identity == SoftwareIdentity(
        repository_revision=None,
        worktree_clean=None,
    )


def test_software_identity_rejects_invalid_values():
    with pytest.raises(
        ValueError,
        match="repository_revision",
    ):
        SoftwareIdentity(
            repository_revision=" ",
            worktree_clean=True,
        )

    with pytest.raises(
        TypeError,
        match="worktree_clean",
    ):
        SoftwareIdentity(
            repository_revision=REVISION,
            worktree_clean="yes",
        )
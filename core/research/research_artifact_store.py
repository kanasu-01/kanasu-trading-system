"""Content-addressed immutable persistence for research artifacts."""

from datetime import datetime
import hashlib

from core.backtest.backtest_result import BacktestResult
import os
from pathlib import Path
import re
import tempfile

from core.research.models.backtest_run_manifest import BacktestRunManifest
from core.research.models.research_catalog import (
    ResearchArtifact,
    ResearchArtifactKind,
)
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    BACKTEST_RUN_MANIFEST_SCHEMA,
    backtest_run_manifest_bytes,
    stable_backtest_result_bytes,
)


_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


def _require_artifact_id(artifact_id: str) -> None:
    if (
        not isinstance(artifact_id, str)
        or not _FINGERPRINT_PATTERN.fullmatch(artifact_id)
    ):
        raise ValueError(
            "artifact_id must use sha256:<64 lowercase hexadecimal>"
        )


def _artifact_id(payload: bytes) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}"


def _relative_path(artifact_id: str) -> str:
    _require_artifact_id(artifact_id)
    digest = artifact_id.removeprefix("sha256:")
    return f"sha256/{digest[:2]}/{digest}.json"


def research_artifact_reference(artifact_id: str) -> str:
    """Return a machine-independent logical reference."""

    _require_artifact_id(artifact_id)
    return f"artifact:{artifact_id}"


class ContentAddressedResearchArtifactStore:
    """Persist immutable artifact bytes under their SHA-256 identity."""

    def __init__(self, root_directory: str | Path):
        self.root_directory = Path(root_directory)
        self.root_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _absolute_path(self, artifact_id: str) -> Path:
        relative = _relative_path(artifact_id)
        return self.root_directory.joinpath(*relative.split("/"))

    @staticmethod
    def _verify_identity(
        path: Path,
        artifact_id: str,
    ) -> bytes:
        payload = path.read_bytes()
        actual_id = _artifact_id(payload)

        if actual_id != artifact_id:
            raise RuntimeError(
                "stored artifact content does not match its identity"
            )

        return payload

    @staticmethod
    def _metadata(
        payload: bytes,
        *,
        artifact_kind: ResearchArtifactKind,
        schema_id: str,
        created_at: datetime,
    ) -> ResearchArtifact:
        artifact_id = _artifact_id(payload)

        # Construct metadata before filesystem publication so invalid
        # metadata cannot create an artifact file.
        return ResearchArtifact(
            artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            schema_id=schema_id,
            relative_path=_relative_path(artifact_id),
            byte_count=len(payload),
            created_at=created_at,
        )

    def persist_bytes(
        self,
        payload: bytes,
        *,
        artifact_kind: ResearchArtifactKind,
        schema_id: str,
        created_at: datetime,
    ) -> ResearchArtifact:
        """Publish exact bytes once and return immutable metadata."""

        if type(payload) is not bytes:
            raise TypeError("artifact payload must be exact bytes")

        artifact = self._metadata(
            payload,
            artifact_kind=artifact_kind,
            schema_id=schema_id,
            created_at=created_at,
        )

        final_path = self._absolute_path(
            artifact.artifact_id
        )

        final_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if final_path.exists():
            existing = final_path.read_bytes()

            if existing != payload:
                raise RuntimeError(
                    "content-addressed artifact conflict; "
                    "existing bytes will not be overwritten"
                )

            self._verify_identity(
                final_path,
                artifact.artifact_id,
            )

            return artifact

        descriptor, temp_name = tempfile.mkstemp(
            prefix=(
                "."
                + artifact.artifact_id.removeprefix("sha256:")
                + "."
            ),
            suffix=".tmp",
            dir=final_path.parent,
        )
        temp_path = Path(temp_name)

        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

            temporary_payload = temp_path.read_bytes()

            if temporary_payload != payload:
                raise RuntimeError(
                    "temporary artifact bytes differ from requested payload"
                )

            if (
                _artifact_id(temporary_payload)
                != artifact.artifact_id
            ):
                raise RuntimeError(
                    "temporary artifact identity verification failed"
                )

            try:
                # Atomic no-overwrite publication in the same filesystem.
                os.link(
                    temp_path,
                    final_path,
                )
            except FileExistsError:
                existing = final_path.read_bytes()

                if existing != payload:
                    raise RuntimeError(
                        "content-addressed artifact conflict; "
                        "existing bytes will not be overwritten"
                    )
        finally:
            if temp_path.exists():
                temp_path.unlink()

        published_payload = self._verify_identity(
            final_path,
            artifact.artifact_id,
        )

        if published_payload != payload:
            raise RuntimeError(
                "published artifact bytes differ from requested payload"
            )

        return artifact

    def load_bytes(self, artifact_id: str) -> bytes:
        """Load and verify one artifact by content identity."""

        _require_artifact_id(artifact_id)
        path = self._absolute_path(artifact_id)

        if not path.is_file():
            raise FileNotFoundError(
                f"research artifact does not exist: {artifact_id}"
            )

        return self._verify_identity(
            path,
            artifact_id,
        )

    def persist_backtest_manifest(
        self,
        manifest: BacktestRunManifest,
        *,
        created_at: datetime,
    ) -> ResearchArtifact:
        """Persist the existing canonical Backtest manifest bytes."""

        return self.persist_bytes(
            backtest_run_manifest_bytes(manifest),
            artifact_kind=ResearchArtifactKind.BACKTEST_RUN_MANIFEST,
            schema_id=BACKTEST_RUN_MANIFEST_SCHEMA,
            created_at=created_at,
        )

    def persist_backtest_result(
        self,
        result: BacktestResult,
        *,
        created_at: datetime,
    ) -> ResearchArtifact:
        """Persist the exact canonical stable Backtest result bytes."""

        return self.persist_bytes(
            stable_backtest_result_bytes(result),
            artifact_kind=ResearchArtifactKind.BACKTEST_RESULT,
            schema_id=BACKTEST_RESULT_SCHEMA,
            created_at=created_at,
        )

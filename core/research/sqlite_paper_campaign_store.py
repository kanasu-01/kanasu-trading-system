"""SQLite persistence for M9.7 qualified Paper campaigns."""

from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3

from core.research.models.paper_campaign import (
    PaperCampaign,
    PaperCampaignHistory,
    PaperCampaignSession,
    PaperCampaignSessionState,
)
from core.research.research_schema import initialize_research_schema


class PaperCampaignAuthorityConflict(ValueError):
    """Expected qualified Paper authority is no longer current at durable write."""


class SQLitePaperCampaignStore:
    """Persist immutable campaigns and append/transition Paper session history."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            initialize_research_schema(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _campaign_from_row(row) -> PaperCampaign:
        return PaperCampaign(
            campaign_id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            candidate_revision_id=row[2],
            wfa_decision_id=row[3],
            study_revision_id=row[4],
            trial_id=row[5],
            experiment_spec_id=row[6],
            parameter_configuration_fingerprint=row[7],
            configuration_fingerprint=row[8],
            created_repository_revision=row[9],
        )

    @staticmethod
    def _session_from_row(row) -> PaperCampaignSession:
        return PaperCampaignSession(
            session_id=row[0],
            campaign_id=row[1],
            created_at=datetime.fromisoformat(row[2]),
            evaluator_repository_revision=row[3],
            live_binding_id=row[4],
            live_provider=row[5],
            live_provider_instrument_id=row[6],
            live_provider_symbol=row[7],
            state=PaperCampaignSessionState(row[8]),
            started_at=(
                None if row[9] is None else datetime.fromisoformat(row[9])
            ),
            terminal_at=(
                None if row[10] is None else datetime.fromisoformat(row[10])
            ),
            terminal_snapshot_json=row[11],
            failure_type=row[12],
            failure_message=row[13],
        )

    @staticmethod
    def _require_current_qualified_authority(
        connection: sqlite3.Connection,
        campaign: PaperCampaign,
    ) -> None:
        row = connection.execute(
            """
            WITH active_policy AS (
                SELECT policy_id
                FROM qualification_policy_activations
                ORDER BY activation_sequence DESC
                LIMIT 1
            ),
            latest_wfa AS (
                SELECT *
                FROM candidate_wfa_decisions
                WHERE candidate_revision_id = ?
                ORDER BY decision_sequence DESC
                LIMIT 1
            ),
            latest_historical AS (
                SELECT q.*
                FROM qualification_decisions AS q
                JOIN active_policy AS p ON p.policy_id = q.policy_id
                WHERE q.trial_id = ?
                ORDER BY q.decision_sequence DESC
                LIMIT 1
            )
            SELECT 1
            FROM latest_wfa AS w
            JOIN latest_historical AS h
              ON h.decision_id = w.historical_qualification_decision_id
            WHERE w.decision_id = ?
              AND w.study_revision_id = ?
              AND w.trial_id = ?
              AND w.candidate_revision_id = ?
              AND w.evidence_validity = 'VALID'
              AND w.wfa_verdict = 'PASS'
              AND w.outcome = 'ELIGIBLE'
              AND h.outcome = 'ELIGIBLE'
              AND h.candidate_revision_id = w.candidate_revision_id
            """,
            (
                campaign.candidate_revision_id,
                campaign.trial_id,
                campaign.wfa_decision_id,
                campaign.study_revision_id,
                campaign.trial_id,
                campaign.candidate_revision_id,
            ),
        ).fetchone()
        if row is None:
            raise PaperCampaignAuthorityConflict(
                "qualified Paper authority changed before durable persistence"
            )

    def create_campaign(self, campaign: PaperCampaign) -> PaperCampaign:
        if not isinstance(campaign, PaperCampaign):
            raise TypeError("campaign must be a PaperCampaign")

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._require_current_qualified_authority(connection, campaign)
                connection.execute(
                    """
                    INSERT INTO paper_campaigns (
                        campaign_id, created_at, candidate_revision_id,
                        wfa_decision_id, study_revision_id, trial_id,
                        experiment_spec_id,
                        parameter_configuration_fingerprint,
                        configuration_fingerprint,
                        created_repository_revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        campaign.campaign_id,
                        campaign.created_at.isoformat(timespec="microseconds"),
                        campaign.candidate_revision_id,
                        campaign.wfa_decision_id,
                        campaign.study_revision_id,
                        campaign.trial_id,
                        campaign.experiment_spec_id,
                        campaign.parameter_configuration_fingerprint,
                        campaign.configuration_fingerprint,
                        campaign.created_repository_revision,
                    ),
                )
            except sqlite3.IntegrityError as error:
                connection.rollback()
                existing = self.load_campaign(campaign.campaign_id)
                if existing == campaign:
                    return existing
                raise ValueError(
                    "PaperCampaign identity already has different data"
                ) from error
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()
        return campaign

    def load_campaign(self, campaign_id: str) -> PaperCampaign | None:
        if not isinstance(campaign_id, str) or not campaign_id:
            raise ValueError("campaign_id must be a non-empty string")
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    campaign_id, created_at, candidate_revision_id,
                    wfa_decision_id, study_revision_id, trial_id,
                    experiment_spec_id,
                    parameter_configuration_fingerprint,
                    configuration_fingerprint,
                    created_repository_revision
                FROM paper_campaigns
                WHERE campaign_id = ?
                """,
                (campaign_id,),
            ).fetchone()
        return None if row is None else self._campaign_from_row(row)

    def create_or_load_matching_campaign(
        self,
        campaign: PaperCampaign,
    ) -> tuple[PaperCampaign, bool]:
        """Atomically validate, reuse one exact campaign, or create it."""

        if not isinstance(campaign, PaperCampaign):
            raise TypeError("campaign must be a PaperCampaign")

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                self._require_current_qualified_authority(connection, campaign)
                row = connection.execute(
                    """
                    SELECT
                        campaign_id, created_at, candidate_revision_id,
                        wfa_decision_id, study_revision_id, trial_id,
                        experiment_spec_id,
                        parameter_configuration_fingerprint,
                        configuration_fingerprint,
                        created_repository_revision
                    FROM paper_campaigns
                    WHERE candidate_revision_id = ?
                      AND wfa_decision_id = ?
                      AND configuration_fingerprint = ?
                    ORDER BY created_at, campaign_id
                    LIMIT 1
                    """,
                    (
                        campaign.candidate_revision_id,
                        campaign.wfa_decision_id,
                        campaign.configuration_fingerprint,
                    ),
                ).fetchone()
                if row is not None:
                    existing = self._campaign_from_row(row)
                    connection.commit()
                    return existing, False

                connection.execute(
                    """
                    INSERT INTO paper_campaigns (
                        campaign_id, created_at, candidate_revision_id,
                        wfa_decision_id, study_revision_id, trial_id,
                        experiment_spec_id,
                        parameter_configuration_fingerprint,
                        configuration_fingerprint,
                        created_repository_revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        campaign.campaign_id,
                        campaign.created_at.isoformat(timespec="microseconds"),
                        campaign.candidate_revision_id,
                        campaign.wfa_decision_id,
                        campaign.study_revision_id,
                        campaign.trial_id,
                        campaign.experiment_spec_id,
                        campaign.parameter_configuration_fingerprint,
                        campaign.configuration_fingerprint,
                        campaign.created_repository_revision,
                    ),
                )
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()
                return campaign, True

    def list_campaigns_for_study(
        self,
        study_id: str,
    ) -> tuple[PaperCampaign, ...]:
        if not isinstance(study_id, str) or not study_id:
            raise ValueError("study_id must be a non-empty string")
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    c.campaign_id, c.created_at, c.candidate_revision_id,
                    c.wfa_decision_id, c.study_revision_id, c.trial_id,
                    c.experiment_spec_id,
                    c.parameter_configuration_fingerprint,
                    c.configuration_fingerprint,
                    c.created_repository_revision
                FROM paper_campaigns AS c
                JOIN study_revisions AS r
                  ON r.study_revision_id = c.study_revision_id
                WHERE r.study_id = ?
                ORDER BY c.created_at, c.campaign_id
                """,
                (study_id,),
            ).fetchall()
        return tuple(self._campaign_from_row(row) for row in rows)

    def list_campaigns_for_candidate(
        self,
        candidate_revision_id: str,
    ) -> tuple[PaperCampaign, ...]:
        if not isinstance(candidate_revision_id, str) or not candidate_revision_id:
            raise ValueError(
                "candidate_revision_id must be a non-empty string"
            )
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    campaign_id, created_at, candidate_revision_id,
                    wfa_decision_id, study_revision_id, trial_id,
                    experiment_spec_id,
                    parameter_configuration_fingerprint,
                    configuration_fingerprint,
                    created_repository_revision
                FROM paper_campaigns
                WHERE candidate_revision_id = ?
                ORDER BY created_at, campaign_id
                """,
                (candidate_revision_id,),
            ).fetchall()
        return tuple(self._campaign_from_row(row) for row in rows)

    def register_session(self, session: PaperCampaignSession) -> None:
        if not isinstance(session, PaperCampaignSession):
            raise TypeError("session must be a PaperCampaignSession")
        if session.state is not PaperCampaignSessionState.CREATED:
            raise ValueError("new campaign session must begin in CREATED")

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                campaign_row = connection.execute(
                    """
                    SELECT
                        campaign_id, created_at, candidate_revision_id,
                        wfa_decision_id, study_revision_id, trial_id,
                        experiment_spec_id,
                        parameter_configuration_fingerprint,
                        configuration_fingerprint,
                        created_repository_revision
                    FROM paper_campaigns
                    WHERE campaign_id = ?
                    """,
                    (session.campaign_id,),
                ).fetchone()
                if campaign_row is None:
                    raise ValueError("PaperCampaign does not exist")
                campaign = self._campaign_from_row(campaign_row)
                self._require_current_qualified_authority(connection, campaign)

                if session.created_at < campaign.created_at:
                    raise ValueError(
                        "Paper campaign session cannot precede campaign creation"
                    )

                active = connection.execute(
                    """
                    SELECT session_id
                    FROM paper_campaign_sessions
                    WHERE state IN ('CREATED', 'RUNNING')
                    ORDER BY session_sequence
                    LIMIT 1
                    """
                ).fetchone()
                if active is not None:
                    raise ValueError(
                        "a durable qualified Paper session is already active"
                    )

                connection.execute(
                    """
                    INSERT INTO paper_campaign_sessions (
                        session_id, campaign_id, created_at,
                        evaluator_repository_revision,
                        live_binding_id, live_provider,
                        live_provider_instrument_id, live_provider_symbol,
                        state, started_at, terminal_at,
                        terminal_snapshot_json, failure_type, failure_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL)
                    """,
                    (
                        session.session_id,
                        session.campaign_id,
                        session.created_at.isoformat(timespec="microseconds"),
                        session.evaluator_repository_revision,
                        session.live_binding_id,
                        session.live_provider,
                        session.live_provider_instrument_id,
                        session.live_provider_symbol,
                        session.state.value,
                    ),
                )
            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ValueError(
                    "Paper campaign session identity must be unique"
                ) from error
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    def load_session(self, session_id: str) -> PaperCampaignSession | None:
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a non-empty string")
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    session_id, campaign_id, created_at,
                    evaluator_repository_revision,
                    live_binding_id, live_provider,
                    live_provider_instrument_id, live_provider_symbol,
                    state, started_at, terminal_at,
                    terminal_snapshot_json, failure_type, failure_message
                FROM paper_campaign_sessions
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return None if row is None else self._session_from_row(row)

    def load_active_session(self) -> PaperCampaignSession | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    session_id, campaign_id, created_at,
                    evaluator_repository_revision,
                    live_binding_id, live_provider,
                    live_provider_instrument_id, live_provider_symbol,
                    state, started_at, terminal_at,
                    terminal_snapshot_json, failure_type, failure_message
                FROM paper_campaign_sessions
                WHERE state IN ('CREATED', 'RUNNING')
                ORDER BY session_sequence
                LIMIT 1
                """
            ).fetchone()
        return None if row is None else self._session_from_row(row)

    def mark_running_if_created(
        self,
        session_id: str,
        *,
        started_at: datetime,
    ) -> PaperCampaignSession:
        if started_at.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware")
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    "SELECT state, created_at, started_at "
                    "FROM paper_campaign_sessions WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("Paper campaign session does not exist")
                state = PaperCampaignSessionState(row[0])
                created_at = datetime.fromisoformat(row[1])
                if started_at < created_at:
                    raise ValueError(
                        "started_at cannot precede durable session creation"
                    )
                if state is PaperCampaignSessionState.CREATED:
                    connection.execute(
                        """
                        UPDATE paper_campaign_sessions
                        SET state = 'RUNNING', started_at = ?
                        WHERE session_id = ? AND state = 'CREATED'
                        """,
                        (
                            started_at.isoformat(timespec="microseconds"),
                            session_id,
                        ),
                    )
                elif state is PaperCampaignSessionState.RUNNING:
                    existing_started_at = datetime.fromisoformat(row[2])
                    if existing_started_at != started_at:
                        raise ValueError(
                            "RUNNING Paper campaign start evidence is immutable"
                        )
                else:
                    connection.commit()
                    loaded = self.load_session(session_id)
                    if loaded is None:
                        raise RuntimeError("Paper campaign session disappeared")
                    return loaded
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()
        loaded = self.load_session(session_id)
        if loaded is None:
            raise RuntimeError("Paper campaign session disappeared")
        return loaded

    def terminalize_session(
        self,
        session_id: str,
        *,
        state: PaperCampaignSessionState,
        terminal_at: datetime,
        terminal_snapshot_json: str | None,
        failure_type: str | None,
        failure_message: str | None,
    ) -> PaperCampaignSession:
        if state not in {
            PaperCampaignSessionState.STOPPED,
            PaperCampaignSessionState.FAILED,
        }:
            raise ValueError("terminalize_session supports STOPPED or FAILED")
        if terminal_at.utcoffset() is None:
            raise ValueError("terminal_at must be timezone-aware")

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT
                        state, created_at, started_at, terminal_at,
                        terminal_snapshot_json, failure_type, failure_message
                    FROM paper_campaign_sessions
                    WHERE session_id = ?
                    """,
                    (session_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("Paper campaign session does not exist")
                current = PaperCampaignSessionState(row[0])
                created_at = datetime.fromisoformat(row[1])
                started_at = (
                    None
                    if row[2] is None
                    else datetime.fromisoformat(row[2])
                )
                if terminal_at < created_at or (
                    started_at is not None
                    and terminal_at < started_at
                ):
                    raise ValueError(
                        "terminal_at cannot precede durable session chronology"
                    )

                if current is PaperCampaignSessionState.INTERRUPTED:
                    raise ValueError(
                        "interrupted Paper campaign session cannot be rewritten"
                    )
                if current in {
                    PaperCampaignSessionState.STOPPED,
                    PaperCampaignSessionState.FAILED,
                }:
                    existing_terminal_at = datetime.fromisoformat(row[3])
                    if (
                        current is not state
                        or existing_terminal_at != terminal_at
                        or row[4] != terminal_snapshot_json
                        or row[5] != failure_type
                        or row[6] != failure_message
                    ):
                        raise ValueError(
                            "terminal Paper campaign evidence is append-only"
                        )
                    connection.commit()
                    loaded = self.load_session(session_id)
                    if loaded is None:
                        raise RuntimeError("Paper campaign session disappeared")
                    return loaded

                cursor = connection.execute(
                    """
                    UPDATE paper_campaign_sessions
                    SET state = ?, terminal_at = ?, terminal_snapshot_json = ?,
                        failure_type = ?, failure_message = ?
                    WHERE session_id = ? AND state IN ('CREATED', 'RUNNING')
                    """,
                    (
                        state.value,
                        terminal_at.isoformat(timespec="microseconds"),
                        terminal_snapshot_json,
                        failure_type,
                        failure_message,
                        session_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "Paper campaign session terminal transition lost authority"
                    )
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

        loaded = self.load_session(session_id)
        if loaded is None:
            raise RuntimeError("Paper campaign session disappeared")
        return loaded

    def recover_incomplete_sessions(
        self,
        *,
        terminal_at: datetime,
    ) -> int:
        if terminal_at.utcoffset() is None:
            raise ValueError("terminal_at must be timezone-aware")

        recovered = 0
        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                rows = connection.execute(
                    """
                    SELECT session_id, created_at, started_at
                    FROM paper_campaign_sessions
                    WHERE state IN ('CREATED', 'RUNNING')
                    ORDER BY session_sequence
                    """
                ).fetchall()

                for session_id, created_text, started_text in rows:
                    effective_terminal = terminal_at
                    created_at = datetime.fromisoformat(created_text)
                    started_at = (
                        None
                        if started_text is None
                        else datetime.fromisoformat(started_text)
                    )
                    for boundary in (created_at, started_at):
                        if (
                            boundary is not None
                            and boundary > effective_terminal
                        ):
                            effective_terminal = boundary

                    cursor = connection.execute(
                        """
                        UPDATE paper_campaign_sessions
                        SET state = 'INTERRUPTED', terminal_at = ?,
                            terminal_snapshot_json = NULL,
                            failure_type = 'ApplicationRestart',
                            failure_message =
                                'prior process ended before a terminal Paper snapshot was durably recorded'
                        WHERE session_id = ?
                          AND state IN ('CREATED', 'RUNNING')
                        """,
                        (
                            effective_terminal.isoformat(
                                timespec="microseconds"
                            ),
                            session_id,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "Paper campaign restart recovery lost session authority"
                        )
                    recovered += 1
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

        return recovered

    def list_sessions(
        self,
        campaign_id: str,
    ) -> tuple[PaperCampaignSession, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    session_id, campaign_id, created_at,
                    evaluator_repository_revision,
                    live_binding_id, live_provider,
                    live_provider_instrument_id, live_provider_symbol,
                    state, started_at, terminal_at,
                    terminal_snapshot_json, failure_type, failure_message
                FROM paper_campaign_sessions
                WHERE campaign_id = ?
                ORDER BY session_sequence
                """,
                (campaign_id,),
            ).fetchall()
        return tuple(self._session_from_row(row) for row in rows)

    def load_history(self, campaign_id: str) -> PaperCampaignHistory | None:
        campaign = self.load_campaign(campaign_id)
        if campaign is None:
            return None
        return PaperCampaignHistory(
            campaign=campaign,
            sessions=self.list_sessions(campaign_id),
        )

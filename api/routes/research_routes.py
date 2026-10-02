from datetime import datetime, timezone
import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from core.market_data.historical_coverage import (
    TimeRange,
)
from core.research.models.registered_study import (
    EvidenceReusePolicy,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)

from api.models.common_models import (
    ApiErrorResponse,
)
from api.models.research_models import (
    ResearchAggregationResponse,
    ResearchProgressResponse,
    ResearchRevisionRegistrationRequest,
    ResearchRevisionRegistrationResponse,
    ResearchStudyCreateRequest,
    ResearchStudyResponse,
    ResearchTrialDetailResponse,
    ResearchTrialListResponse,
)
from api.research_application import (
    ResearchRevisionNotFound,
    ResearchStudyNotFound,
    ResearchTrialNotFound,
    cancel_research_revision as cancel_research_revision_application,
    create_research_study as create_research_study_application,
    get_research_aggregation as get_research_aggregation_application,
    get_research_progress as get_research_progress_application,
    get_research_trial_detail as get_research_trial_detail_application,
    list_research_trials as list_research_trials_application,
    register_research_revision as register_research_revision_application,
    reopen_research_study as reopen_research_study_application,
    start_research_revision as start_research_revision_application,
)


router = APIRouter()
logger = logging.getLogger(__name__)


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
) -> JSONResponse:
    error = ApiErrorResponse(
        code=code,
        message=message,
    )

    return JSONResponse(
        status_code=status_code,
        content=error.model_dump(),
    )


@router.post(
    "/studies",
    response_model=ResearchStudyResponse,
    responses={
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def create_research_study(
    request: ResearchStudyCreateRequest,
):
    try:
        return await run_in_threadpool(
            create_research_study_application,
            request.display_title,
        )

    except ValueError:
        return _error_response(
            status_code=422,
            code="invalid_research_study",
            message="Research study request was invalid",
        )

    except Exception:
        logger.exception(
            "Research Study creation failed"
        )

        return _error_response(
            status_code=500,
            code="research_study_create_failed",
            message="Research study could not be created",
        )


@router.post(
    "/studies/{study_id}/revisions",
    response_model=ResearchRevisionRegistrationResponse,
    responses={
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def register_research_revision(
    study_id: str,
    request: ResearchRevisionRegistrationRequest,
):
    try:
        definition = UniverseDefinition(
            name=request.universe_definition.name,
            selection_spec=(
                request.universe_definition.selection_spec
            ),
            source_reference=(
                request.universe_definition.source_reference
            ),
        )

        research_range = TimeRange(
            start=request.research_range.start,
            end=request.research_range.end,
        )

        snapshots = tuple(
            UniverseSnapshot(
                definition=definition,
                members=tuple(
                    snapshot.members
                ),
                quality=UniverseQuality(
                    snapshot.quality
                ),
                as_of=snapshot.as_of,
                provenance_refs=tuple(
                    snapshot.provenance_refs
                ),
                effective_from=(
                    snapshot.effective_from
                ),
                effective_to=(
                    snapshot.effective_to
                ),
                derivation_version=(
                    snapshot.derivation_version
                ),
            )
            for snapshot
            in request.universe_snapshots
        )

        return await run_in_threadpool(
            register_research_revision_application,
            study_id=study_id,
            research_intent=request.research_intent,
            strategy_procedure_id=(
                request.strategy_procedure_id
            ),
            timeframe=request.timeframe,
            research_range=research_range,
            timezone=request.timezone,
            initial_capital=request.initial_capital,
            risk_economic_configuration=(
                request.risk_economic_configuration
            ),
            parameter_variants=tuple(
                request.parameter_variants
            ),
            universe_definition=definition,
            universe_snapshots=snapshots,
            require_point_in_time=(
                request.require_point_in_time
            ),
            data_treatment_basis=(
                request.data_treatment_basis
            ),
            repository_revision=(
                request.repository_revision
            ),
            evidence_reuse_policy=(
                EvidenceReusePolicy(
                    request.evidence_reuse_policy
                )
            ),
            registered_at=datetime.now(
                timezone.utc
            ),
        )

    except ResearchStudyNotFound:
        return _error_response(
            status_code=404,
            code="research_study_not_found",
            message="Research study was not found",
        )

    except (TypeError, ValueError):
        return _error_response(
            status_code=422,
            code="invalid_research_registration",
            message=(
                "Research revision registration "
                "was invalid"
            ),
        )

    except Exception:
        logger.exception(
            "Research revision registration failed"
        )

        return _error_response(
            status_code=500,
            code="research_registration_failed",
            message=(
                "Research revision could not be registered"
            ),
        )


@router.post(
    "/studies/{study_id}/reopen",
    response_model=ResearchStudyResponse,
    responses={
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def reopen_research_study(
    study_id: str,
):
    try:
        return await run_in_threadpool(
            reopen_research_study_application,
            study_id,
        )

    except ResearchStudyNotFound:
        return _error_response(
            status_code=404,
            code="research_study_not_found",
            message="Research study was not found",
        )

    except ValueError:
        return _error_response(
            status_code=422,
            code="invalid_research_study",
            message="Research study request was invalid",
        )

    except Exception:
        logger.exception(
            "Research Study reopen failed"
        )

        return _error_response(
            status_code=500,
            code="research_study_reopen_failed",
            message="Research study could not be reopened",
        )


@router.get(
    "/study-revisions/{study_revision_id}/progress",
    response_model=ResearchProgressResponse,
    responses={
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def get_research_progress(
    study_revision_id: str,
):
    try:
        return await run_in_threadpool(
            get_research_progress_application,
            study_revision_id,
        )

    except ResearchRevisionNotFound:
        return _error_response(
            status_code=404,
            code="research_revision_not_found",
            message="Research revision was not found",
        )

    except Exception:
        logger.exception(
            "Research progress load failed"
        )

        return _error_response(
            status_code=500,
            code="research_progress_failed",
            message=(
                "Research progress could not be loaded"
            ),
        )


@router.get(
    "/study-revisions/{study_revision_id}/trials",
    response_model=ResearchTrialListResponse,
    responses={
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def list_research_trials(
    study_revision_id: str,
):
    try:
        return await run_in_threadpool(
            list_research_trials_application,
            study_revision_id,
        )

    except ResearchRevisionNotFound:
        return _error_response(
            status_code=404,
            code="research_revision_not_found",
            message="Research revision was not found",
        )

    except Exception:
        logger.exception(
            "Research Trial list load failed"
        )

        return _error_response(
            status_code=500,
            code="research_trial_list_failed",
            message=(
                "Research trials could not be loaded"
            ),
        )


@router.get(
    "/trials/{trial_id}",
    response_model=ResearchTrialDetailResponse,
    responses={
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def get_research_trial_detail(
    trial_id: str,
):
    try:
        return await run_in_threadpool(
            get_research_trial_detail_application,
            trial_id,
        )

    except ResearchTrialNotFound:
        return _error_response(
            status_code=404,
            code="research_trial_not_found",
            message="Research trial was not found",
        )

    except Exception:
        logger.exception(
            "Research Trial detail load failed"
        )

        return _error_response(
            status_code=500,
            code="research_trial_detail_failed",
            message=(
                "Research trial detail could not be loaded"
            ),
        )


@router.get(
    "/study-revisions/{study_revision_id}/aggregation",
    response_model=ResearchAggregationResponse,
    responses={
        404: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def get_research_aggregation(
    study_revision_id: str,
):
    try:
        return await run_in_threadpool(
            get_research_aggregation_application,
            study_revision_id,
        )

    except ResearchRevisionNotFound:
        return _error_response(
            status_code=404,
            code="research_revision_not_found",
            message="Research revision was not found",
        )

    except Exception:
        logger.exception(
            "Research aggregation load failed"
        )

        return _error_response(
            status_code=500,
            code="research_aggregation_failed",
            message=(
                "Research aggregation could not be loaded"
            ),
        )


@router.post(
    "/study-revisions/{study_revision_id}/start",
    response_model=ResearchProgressResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def start_research_revision(
    study_revision_id: str,
):
    try:
        return await run_in_threadpool(
            start_research_revision_application,
            study_revision_id,
            started_at=datetime.now(
                timezone.utc
            ),
        )

    except ResearchRevisionNotFound:
        return _error_response(
            status_code=404,
            code="research_revision_not_found",
            message="Research revision was not found",
        )

    except ValueError:
        return _error_response(
            status_code=409,
            code="research_revision_start_conflict",
            message=(
                "Research revision could not be started "
                "in its current state"
            ),
        )

    except Exception:
        logger.exception(
            "Research revision start failed"
        )

        return _error_response(
            status_code=500,
            code="research_revision_start_failed",
            message="Research revision could not be started",
        )


@router.post(
    "/study-revisions/{study_revision_id}/cancel",
    response_model=ResearchProgressResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def cancel_research_revision(
    study_revision_id: str,
):
    try:
        return await run_in_threadpool(
            cancel_research_revision_application,
            study_revision_id,
            requested_at=datetime.now(
                timezone.utc
            ),
        )

    except ResearchRevisionNotFound:
        return _error_response(
            status_code=404,
            code="research_revision_not_found",
            message="Research revision was not found",
        )

    except ValueError:
        return _error_response(
            status_code=409,
            code="research_revision_cancel_conflict",
            message=(
                "Research revision could not be cancelled "
                "in its current state"
            ),
        )

    except Exception:
        logger.exception(
            "Research revision cancellation failed"
        )

        return _error_response(
            status_code=500,
            code="research_revision_cancel_failed",
            message=(
                "Research revision could not be cancelled"
            ),
        )

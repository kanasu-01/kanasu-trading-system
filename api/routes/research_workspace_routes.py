"""HTTP boundary for the M9.8 research workspace."""

import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from api.models.common_models import ApiErrorResponse
from api.paper_trading_application import PaperLifecycleConflict
from api.models.research_workspace_models import (
    ResearchWorkspaceConfigResponse,
    WorkspaceBacktestRunRequest,
    WorkspaceBacktestRunResponse,
    WorkspacePaperCampaignListResponse,
    WorkspacePaperHistoryResponse,
    WorkspacePaperSendRequest,
    WorkspacePaperSendResponse,
    WorkspacePaperStartRequest,
    WorkspacePaperStopRequest,
    WorkspaceQualificationRequest,
    WorkspaceQualificationResponse,
    WorkspaceRetryRequest,
    WorkspaceStrategyListResponse,
    WorkspaceStrategyState,
    WorkspaceStudyCreateRequest,
    WorkspaceStudyResponse,
    WorkspaceWfaResponse,
    WorkspaceWfaRunRequest,
)
from api.research_workspace_application import (
    ResearchWorkspaceConflict,
    ResearchWorkspaceNotFound,
    ResearchWorkspaceOperationalError,
    build_research_workspace_application,
)
from core.research.qualified_paper_campaign_service import (
    PaperCampaignLifecycleConflict,
    PaperCampaignNotFound,
    QualifiedPaperAdmissionError,
    QualifiedPaperOperationalError,
)


router = APIRouter()
logger = logging.getLogger(__name__)


def workspace_application_factory():
    return build_research_workspace_application()


def _error(status_code: int, code: str, message: str):
    return JSONResponse(
        status_code=status_code,
        content=ApiErrorResponse(code=code, message=message).model_dump(),
    )


@router.get(
    "/config",
    response_model=ResearchWorkspaceConfigResponse,
    responses={500: {"model": ApiErrorResponse}},
)
async def get_workspace_config():
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(app.config)
    except Exception:
        logger.exception("Research workspace config failed")
        return _error(
            500,
            "research_workspace_config_failed",
            "Research workspace configuration could not be loaded",
        )


@router.post(
    "/studies",
    response_model=WorkspaceStudyResponse,
    responses={
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def create_study(request: WorkspaceStudyCreateRequest):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(
            app.create_study,
            request.display_title,
        )
    except ValueError:
        return _error(422, "invalid_study", "Study could not be created")
    except Exception:
        logger.exception("Research workspace Study creation failed")
        return _error(
            500,
            "research_workspace_study_failed",
            "Study could not be created",
        )


@router.get(
    "/studies/{study_id}/strategies",
    response_model=WorkspaceStrategyListResponse,
    responses={
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def get_study_strategies(study_id: str):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(app.study_strategies, study_id)
    except ResearchWorkspaceNotFound:
        return _error(404, "study_not_found", "Study was not found")
    except ResearchWorkspaceConflict:
        return _error(
            409,
            "study_state_conflict",
            "Study authority changed while strategy state was being loaded",
        )
    except Exception:
        logger.exception("Research workspace strategy list failed")
        return _error(
            500,
            "research_workspace_strategy_list_failed",
            "Study strategies could not be loaded",
        )


@router.post(
    "/backtests/run",
    response_model=WorkspaceBacktestRunResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def run_registered_backtest(request: WorkspaceBacktestRunRequest):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(app.run_backtest, request)
    except ResearchWorkspaceNotFound:
        return _error(404, "study_not_found", "Study was not found")
    except ResearchWorkspaceConflict:
        return _error(
            409,
            "research_backtest_conflict",
            "Registered Backtest cannot run from its current state",
        )
    except ValueError:
        return _error(
            422,
            "invalid_research_backtest",
            "Registered Backtest inputs are invalid",
        )
    except ResearchWorkspaceOperationalError:
        logger.exception("Registered research Backtest operational failure")
        return _error(
            500,
            "research_backtest_operational_failure",
            "Registered Backtest authority could not be established reliably",
        )
    except Exception:
        logger.exception("Registered research Backtest failed")
        return _error(
            500,
            "research_backtest_failed",
            "Registered Backtest execution failed",
        )


@router.get(
    "/trials/{trial_id}/backtest-result",
    response_model=WorkspaceBacktestRunResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def get_registered_backtest_result(trial_id: str):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(app.load_backtest_result, trial_id)
    except ResearchWorkspaceNotFound:
        return _error(404, "trial_not_found", "Trial was not found")
    except ResearchWorkspaceConflict:
        return _error(
            409,
            "research_backtest_result_unavailable",
            "Trial does not have a saved result-bearing Backtest",
        )
    except ResearchWorkspaceOperationalError:
        logger.exception("Saved registered Backtest result load failed")
        return _error(
            500,
            "research_backtest_result_failed",
            "Saved Backtest result could not be loaded reliably",
        )


@router.post(
    "/trials/{trial_id}/retry",
    response_model=WorkspaceStrategyState,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def retry_registered_backtest(
    trial_id: str,
    request: WorkspaceRetryRequest,
):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(
            app.retry_backtest,
            trial_id,
            request.expected_disposition_event_id,
        )
    except ResearchWorkspaceNotFound:
        return _error(404, "trial_not_found", "Trial was not found")
    except ResearchWorkspaceConflict:
        return _error(
            409,
            "research_retry_conflict",
            "Trial is not retryable from its current state",
        )
    except Exception:
        logger.exception("Registered research Backtest retry failed")
        return _error(
            500,
            "research_retry_failed",
            "Registered Backtest retry failed",
        )


@router.post(
    "/studies/{study_id}/qualification",
    response_model=WorkspaceQualificationResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def qualify_study(
    study_id: str,
    request: WorkspaceQualificationRequest,
):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(
            app.qualify_study,
            study_id,
            request.threshold_pct,
            request.observed_policy_id,
        )
    except ResearchWorkspaceNotFound:
        return _error(404, "study_not_found", "Study was not found")
    except ResearchWorkspaceConflict:
        return _error(
            409,
            "qualification_policy_conflict",
            "Qualification policy could not be changed safely",
        )
    except ResearchWorkspaceOperationalError:
        logger.exception("Study qualification operational failure")
        return _error(
            500,
            "study_qualification_operational_failure",
            "Study qualification authority could not be loaded reliably",
        )
    except Exception:
        logger.exception("Study qualification failed")
        return _error(
            500,
            "study_qualification_failed",
            "Study qualification could not be completed reliably",
        )


@router.get(
    "/studies/{study_id}/wfa",
    response_model=WorkspaceWfaResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def get_wfa(study_id: str):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(app.wfa_state, study_id)
    except ResearchWorkspaceNotFound:
        return _error(404, "study_not_found", "Study was not found")
    except ResearchWorkspaceConflict:
        return _error(
            409,
            "wfa_state_conflict",
            "WFA authority changed while state was being loaded",
        )
    except ResearchWorkspaceOperationalError:
        logger.exception("WFA state operational failure")
        return _error(
            500,
            "wfa_state_operational_failure",
            "WFA authority could not be loaded reliably",
        )
    except Exception:
        logger.exception("WFA state load failed")
        return _error(500, "wfa_state_failed", "WFA state could not be loaded")


@router.post(
    "/studies/{study_id}/wfa/run",
    response_model=WorkspaceWfaResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def run_wfa(study_id: str, request: WorkspaceWfaRunRequest):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(
            app.run_wfa,
            study_id,
            request.expected_policy_id,
        )
    except ResearchWorkspaceNotFound:
        return _error(404, "study_not_found", "Study was not found")
    except ResearchWorkspaceConflict:
        return _error(
            409,
            "wfa_policy_conflict",
            "Qualification policy changed since WFA was observed",
        )
    except Exception:
        logger.exception("Study WFA failed")
        return _error(500, "wfa_run_failed", "WFA could not be completed reliably")


@router.post(
    "/studies/{study_id}/paper/send",
    response_model=WorkspacePaperSendResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def send_to_paper(
    study_id: str,
    request: WorkspacePaperSendRequest,
):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(
            app.send_to_paper,
            study_id,
            request.expected_wfa_decision_ids,
        )
    except ResearchWorkspaceNotFound:
        return _error(404, "study_not_found", "Study was not found")
    except ResearchWorkspaceConflict:
        return _error(
            409,
            "send_to_paper_conflict",
            "Displayed WFA decisions are no longer current",
        )
    except QualifiedPaperAdmissionError:
        return _error(
            409,
            "qualified_paper_admission_failed",
            "One or more strategies are no longer eligible for Paper",
        )
    except QualifiedPaperOperationalError:
        return _error(
            500,
            "qualified_paper_operational_failure",
            "Qualified Paper authority could not be established reliably",
        )
    except Exception:
        logger.exception("Send strategies to Paper failed")
        return _error(
            500,
            "send_to_paper_failed",
            "Strategies could not be sent to Paper",
        )


@router.get(
    "/studies/{study_id}/paper",
    response_model=WorkspacePaperCampaignListResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def get_paper_campaigns(study_id: str):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(app.paper_state, study_id)
    except ResearchWorkspaceNotFound:
        return _error(404, "study_not_found", "Study was not found")
    except ResearchWorkspaceConflict:
        return _error(
            409,
            "paper_campaign_state_conflict",
            "Paper authority changed while campaign state was being loaded",
        )
    except Exception:
        logger.exception("Paper campaign list failed")
        return _error(
            500,
            "paper_campaign_list_failed",
            "Paper campaigns could not be loaded",
        )


@router.get(
    "/paper-campaigns/{campaign_id}/history",
    response_model=WorkspacePaperHistoryResponse,
    responses={
        404: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def get_paper_history(campaign_id: str):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(app.paper_history, campaign_id)
    except PaperCampaignNotFound:
        return _error(404, "paper_campaign_not_found", "Paper campaign was not found")
    except (QualifiedPaperOperationalError, ResearchWorkspaceOperationalError):
        logger.exception("Paper campaign history operational failure")
        return _error(
            500,
            "paper_campaign_history_operational_failure",
            "Paper campaign history could not be loaded reliably",
        )
    except Exception:
        logger.exception("Paper campaign history failed")
        return _error(
            500,
            "paper_campaign_history_failed",
            "Paper campaign history could not be loaded",
        )


@router.post(
    "/paper-campaigns/{campaign_id}/start",
    response_model=WorkspacePaperHistoryResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def start_paper(
    campaign_id: str,
    request: WorkspacePaperStartRequest,
):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(
            app.start_paper,
            campaign_id,
            request.expected_latest_session_id,
        )
    except PaperCampaignNotFound:
        return _error(404, "paper_campaign_not_found", "Paper campaign was not found")
    except QualifiedPaperOperationalError:
        return _error(
            500,
            "qualified_paper_start_operational_failure",
            "Qualified Paper session could not be prepared reliably",
        )
    except (
        QualifiedPaperAdmissionError,
        PaperCampaignLifecycleConflict,
        PaperLifecycleConflict,
    ):
        return _error(
            409,
            "qualified_paper_start_conflict",
            "Qualified Paper session cannot start from the current authority/state",
        )
    except Exception:
        logger.exception("Qualified Paper start failed")
        return _error(
            500,
            "qualified_paper_start_failed",
            "Qualified Paper session failed to start",
        )


@router.post(
    "/paper-campaigns/{campaign_id}/stop",
    response_model=WorkspacePaperHistoryResponse,
    responses={
        404: {"model": ApiErrorResponse},
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def stop_paper(
    campaign_id: str,
    request: WorkspacePaperStopRequest,
):
    try:
        app = workspace_application_factory()
        return await run_in_threadpool(
            app.stop_paper,
            campaign_id,
            request.expected_session_id,
        )
    except PaperCampaignNotFound:
        return _error(404, "paper_campaign_not_found", "Paper campaign was not found")
    except (PaperCampaignLifecycleConflict, PaperLifecycleConflict):
        return _error(
            409,
            "qualified_paper_stop_conflict",
            "Qualified Paper session cannot stop from the current state",
        )
    except Exception:
        logger.exception("Qualified Paper stop failed")
        return _error(
            500,
            "qualified_paper_stop_failed",
            "Qualified Paper session failed to stop",
        )

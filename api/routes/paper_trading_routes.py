import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from api.application_catalog import (
    paper_trading_config_payload,
)
from api.models.common_models import (
    ApiErrorResponse,
)
from api.models.paper_trading_models import (
    PaperTradingConfigResponse,
    PaperTradingStartRequest,
    PaperTradingStartResponse,
    PaperTradingStatusResponse,
    PaperTradingStopResponse,
)
from api.paper_trading_application import (
    PaperLifecycleConflict,
    paper_trading_application,
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


@router.get(
    "/config",
    response_model=PaperTradingConfigResponse,
)
async def get_paper_trading_config(
) -> PaperTradingConfigResponse:
    return PaperTradingConfigResponse.model_validate(
        paper_trading_config_payload()
    )


@router.post(
    "/start",
    response_model=PaperTradingStartResponse,
    responses={
        409: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def start_paper_trading(
    request: PaperTradingStartRequest,
):
    try:
        return await run_in_threadpool(
            paper_trading_application.start,
            request,
        )
    except PaperLifecycleConflict:
        return _error_response(
            status_code=409,
            code="paper_lifecycle_conflict",
            message="Paper trading lifecycle conflict",
        )
    except Exception:
        logger.exception(
            "Paper trading API start failed"
        )

        return _error_response(
            status_code=500,
            code="paper_start_failed",
            message="Paper trading start failed",
        )


@router.get(
    "/status",
    response_model=PaperTradingStatusResponse,
    responses={
        500: {"model": ApiErrorResponse},
    },
)
async def get_paper_trading_status():
    try:
        return await run_in_threadpool(
            paper_trading_application.status
        )
    except Exception:
        logger.exception(
            "Paper trading API status failed"
        )

        return _error_response(
            status_code=500,
            code="paper_status_failed",
            message="Paper trading status failed",
        )


@router.post(
    "/stop",
    response_model=PaperTradingStopResponse,
    responses={
        409: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def stop_paper_trading():
    try:
        return await run_in_threadpool(
            paper_trading_application.stop
        )
    except PaperLifecycleConflict:
        return _error_response(
            status_code=409,
            code="paper_lifecycle_conflict",
            message="Paper trading lifecycle conflict",
        )
    except Exception:
        logger.exception(
            "Paper trading API stop failed"
        )

        return _error_response(
            status_code=500,
            code="paper_stop_failed",
            message="Paper trading stop failed",
        )

import logging

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from api.application_catalog import backtest_config_payload
from api.backtest_application import execute_backtest_request
from api.models.backtest_models import (
    BacktestConfigResponse,
    BacktestRunRequest,
    BacktestRunResponse,
)
from api.models.common_models import ApiErrorResponse


router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/config",
    response_model=BacktestConfigResponse,
)
async def get_backtest_config() -> BacktestConfigResponse:
    return BacktestConfigResponse.model_validate(
        backtest_config_payload()
    )


@router.post(
    "/run",
    response_model=BacktestRunResponse,
    responses={
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    },
)
async def run_backtest(
    request: BacktestRunRequest,
):
    try:
        return await run_in_threadpool(
            execute_backtest_request,
            request,
        )
    except Exception:
        logger.exception(
            "Backtest API execution failed"
        )

        error = ApiErrorResponse(
            code="backtest_execution_failed",
            message="Backtest execution failed",
        )

        return JSONResponse(
            status_code=500,
            content=error.model_dump(),
        )

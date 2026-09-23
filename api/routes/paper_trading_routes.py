from fastapi import APIRouter

from core.paper_trading.paper_trading_service import (
    paper_trading_service,
)

from api.application_catalog import (
    paper_trading_config_payload,
)

from api.models.paper_trading_models import (
    PaperTradingConfigResponse,
    PaperTradingStartRequest,
)

router = APIRouter()


@router.get(
    "/config",
    response_model=PaperTradingConfigResponse,
)
async def get_paper_trading_config(
) -> PaperTradingConfigResponse:
    return PaperTradingConfigResponse.model_validate(
        paper_trading_config_payload()
    )


@router.post("/start")
async def start_paper_trading(
    request: PaperTradingStartRequest,
):

    if paper_trading_service.has_active_session():

        return {
            "status": "already_running",
        }

    session = paper_trading_service.create_session(
        strategy_name=request.strategy_id,
        symbol=request.symbol,
        initial_capital=100000,
    )

    return {
        "session_id": session.session_id,
        "status": session.status,
        "symbol": session.symbol,
        "strategy": session.strategy_name,
    }


@router.post("/stop")
async def stop_paper_trading():

    session = paper_trading_service.get_session()

    if session:

        session.stop()

        paper_trading_service.clear_session()

    return {
        "status": "stopped",
    }


@router.get("/status")
async def get_paper_trading_status():

    session = paper_trading_service.get_session()

    if session is None:

        return {
            "status": "STOPPED",
            "strategy": None,
            "symbol": None,
            "started_at": None,
        }

    snapshot = session.snapshot()

    return {
        "status": snapshot.status,
        "strategy": snapshot.strategy_name,
        "symbol": snapshot.symbol,
        "started_at": snapshot.started_at,
    }

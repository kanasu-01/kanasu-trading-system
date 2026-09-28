from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from api.models.common_models import ApiErrorResponse
from api.routes.backtest_routes import router as backtest_router
from api.routes.paper_trading_routes import (
    router as paper_trading_router,
)
from core.config.loaders import load_app_config
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


load_dotenv()


def recover_stale_research_attempts():
    """Recover durable RUNNING research attempts after application restart."""

    config = load_app_config()
    store = SQLiteResearchCatalogStore(
        config.research_database_path
    )

    return store.recover_running_attempts(
        terminal_at=datetime.now(timezone.utc)
    )


@asynccontextmanager
async def application_lifespan(_app: FastAPI):
    recover_stale_research_attempts()
    yield


app = FastAPI(
    title="Kanasu Trading System API",
    lifespan=application_lifespan,
)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    _request: Request,
    _exc: RequestValidationError,
) -> JSONResponse:
    error = ApiErrorResponse(
        code="invalid_request",
        message="Request validation failed",
    )

    return JSONResponse(
        status_code=422,
        content=error.model_dump(),
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    backtest_router,
    prefix="/api/backtest",
    tags=["Backtest"],
)

app.include_router(
    paper_trading_router,
    prefix="/api/paper-trading",
    tags=["Paper Trading"],
)

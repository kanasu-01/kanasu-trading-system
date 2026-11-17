from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from api.models.common_models import ApiErrorResponse
from api.routes.backtest_routes import router as backtest_router
from api.routes.paper_trading_routes import (
    router as paper_trading_router,
)
from api.routes.research_routes import (
    router as research_router,
)
from api.staging import allowed_origins, auth, require_session, router as staging_router
from core.staging import disable_smartapi_logging, staging_enabled
from core.config.loaders import load_app_config
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)
from core.research.sqlite_paper_campaign_store import (
    SQLitePaperCampaignStore,
)


load_dotenv()


def recover_stale_research_attempts():
    """
    Recover stale durable research execution state after restart.

    ResearchJob recovery is authoritative for linked Trial/Job/Attempt
    lifecycle state. Legacy attempt-only recovery then catches any
    standalone RUNNING RunAttempts that are not owned by a ResearchJob.
    """

    config = load_app_config()
    store = SQLiteResearchCatalogStore(
        config.research_database_path
    )

    terminal_at = datetime.now(timezone.utc)

    store.recover_running_research_jobs(
        terminal_at=terminal_at
    )

    return store.recover_running_attempts(
        terminal_at=terminal_at
    )



def recover_stale_paper_campaign_sessions() -> int:
    """Mark unfinished qualified Paper sessions interrupted after restart."""

    config = load_app_config()
    store = SQLitePaperCampaignStore(
        config.research_database_path
    )
    return store.recover_incomplete_sessions(
        terminal_at=datetime.now(timezone.utc)
    )

@asynccontextmanager
async def application_lifespan(_app: FastAPI):
    # Render is always protected, even when the mode flag is absent/false.
    # Outside staging retain accepted startup behavior and recovery semantics.
    if staging_enabled():
        auth.ready()
        disable_smartapi_logging()
        if load_app_config().enable_live_trading:
            raise RuntimeError("Live trading is prohibited on Render staging")

    recover_stale_research_attempts()
    recover_stale_paper_campaign_sessions()
    yield


app = FastAPI(
    title="Kanasu Trading System API",
    lifespan=application_lifespan,
    docs_url=None if staging_enabled() else "/docs",
    redoc_url=None if staging_enabled() else "/redoc",
    openapi_url=None if staging_enabled() else "/openapi.json",
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


if staging_enabled():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
else:
    # Existing non-staging CORS policy retained.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "available"}


app.include_router(
    staging_router,
    prefix="/api/auth",
    tags=["Staging Authentication"],
)

app.include_router(
    backtest_router,
    prefix="/api/backtest",
    tags=["Backtest"],
    dependencies=[Depends(require_session)],
)

app.include_router(
    paper_trading_router,
    prefix="/api/paper-trading",
    tags=["Paper Trading"],
    dependencies=[Depends(require_session)],
)

app.include_router(
    research_router,
    prefix="/api/research",
    tags=["Research"],
    dependencies=[Depends(require_session)],
)

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.models.common_models import ApiErrorResponse
from api.routes.backtest_routes import router as backtest_router
from api.routes.paper_trading_routes import (
    router as paper_trading_router,
)


app = FastAPI(
    title="Kanasu Trading System API",
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

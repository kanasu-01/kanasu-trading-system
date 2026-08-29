from fastapi import FastAPI

from fastapi.middleware.cors import (
    CORSMiddleware,
)

from api.routes.backtest_routes import (
    router as backtest_router,
)

from api.routes.paper_trading_routes import (
    router as paper_trading_router,
)

app = FastAPI(
    title="Kanasu Trading System API",
)

#
# CORS
#

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#
# ROUTES
#

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

"""Deterministic protected browser fixture; never contacts Angel One."""

from datetime import datetime, timezone
import secrets
from threading import Lock

import api.main as main_module
import api.staging as staging_module
import api.routes.backtest_routes as backtest_routes
import api.routes.paper_trading_routes as paper_routes


class SyntheticPaper:
    def __init__(self):
        self.lock = Lock(); self.active = False; self.snapshot = None

    @staticmethod
    def payload(status: str) -> dict:
        now = "2026-11-16T09:15:00+05:30"
        return {"session_id":"e2e-paper-session","status":status,"strategy_name":"SMA Crossover","symbol":"RELIANCE","started_at":now,"stopped_at":now if status=="STOPPED" else None,"initial_capital":100000.0,"cash":100000.0,"position_size":0.0,"position_value":0.0,"equity":100000.0,"realized_pnl":0.0,"unrealized_pnl":0.0,"total_pnl":0.0,"peak_equity":100000.0,"drawdown":0.0,"active_position":None,"completed_trade_count":0,"last_execution_event":None,"last_execution_price":None,"last_execution_quantity":None,"failure_type":None,"failure_message":None}

    def start(self, _request):
        with self.lock:
            self.active = True; self.snapshot = self.payload("RUNNING"); return self.snapshot

    def status(self):
        with self.lock: return {"active": self.active, "snapshot": self.snapshot}

    def stop(self):
        with self.lock:
            self.active = False; self.snapshot = self.payload("STOPPED"); return self.snapshot


def synthetic_backtest(request):
    z = 0.0
    return {"run_id":"e2e-backtest-run","attempt_id":None,"evidence_id":"e2e-evidence","evidence_status":"ACCEPTED","status":"completed","symbol":request.symbol,"timeframe":request.timeframe,"strategy_id":request.strategy_id,"start":request.start,"end":request.end,"timezone":request.timezone,"summary":{"completed_trade_count":0,"net_profitable_trade_count":0,"net_losing_trade_count":0,"net_breakeven_trade_count":0,"net_profitable_trade_rate_pct":z,"mean_positive_instrument_return_pct":z,"mean_negative_instrument_return_pct":z,"mean_instrument_return_pct":z,"gross_realized_pnl":z,"net_realized_pnl":z,"mean_net_pnl_per_completed_trade":z,"completed_trade_transaction_cost_total":z,"account_pnl":z,"account_return_pct":z,"max_equity_drawdown_pct":z},"equity_curve":[{"timestamp":request.start,"equity":request.initial_capital},{"timestamp":request.end,"equity":request.initial_capital}],"trades":[]}


backtest_routes.execute_backtest_request = synthetic_backtest
paper_routes.paper_trading_application = SyntheticPaper()
app = main_module.app


@app.post("/__test__/simulate-restart")
async def simulate_restart() -> dict[str, str]:
    with staging_module.auth.lock:
        staging_module.auth.sessions.clear()
    staging_module._RUNTIME_ID = secrets.token_urlsafe(18)
    staging_module._RUNTIME_STARTED = datetime.now(timezone.utc).isoformat()
    paper_routes.paper_trading_application = SyntheticPaper()
    return {"status": "simulated-restart"}

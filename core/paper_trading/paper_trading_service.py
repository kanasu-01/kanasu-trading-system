from core.paper_trading.paper_trading_session import (
    PaperTradingSession,
)


class PaperTradingService:
    """
    Owns the currently running paper trading session.

    MVP:
    - Single active session only

    Future:
    - Multiple concurrent sessions
    - Session persistence
    """

    def __init__(self) -> None:

        self._current_session: PaperTradingSession | None = None

    def set_session(
        self,
        session: PaperTradingSession,
    ) -> None:

        self._current_session = session

    def get_session(
        self,
    ) -> PaperTradingSession | None:

        return self._current_session

    def has_active_session(
        self,
    ) -> bool:

        return self._current_session is not None

    def create_session(
        self,
        strategy_name: str,
        symbol: str,
        initial_capital: float,
    ) -> PaperTradingSession:

        session = PaperTradingSession(
            session_id="paper_mock_001",
            strategy_name=strategy_name,
            symbol=symbol,
            initial_capital=initial_capital,
        )

        session.start()

        self._current_session = session

        return session

    def clear_session(
        self,
    ) -> None:

        self._current_session = None


paper_trading_service = PaperTradingService()

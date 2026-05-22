from core.logging.logger import get_logger

from core.walk_forward.result import (
    WalkForwardResult,
)


class WalkForwardReporter:
    """
    Walk-forward reporting and observability.
    """

    def __init__(self):
        self.logger = get_logger(__name__)

    # ------------------------------------------------------
    # Public API
    # ------------------------------------------------------

    def log_summary(
        self,
        result: WalkForwardResult,
    ) -> None:

        self.logger.info("=== WALK-FORWARD RESULT ===")

        self.logger.info(f"VERDICT={result.verdict}")

        # -----------------------------------------
        # Aggregated Metrics
        # -----------------------------------------

        self.logger.info("--- Aggregated Metrics ---")

        for key, value in result.aggregated_metrics.items():
            self.logger.info(f"{key}={value}")

        # -----------------------------------------
        # Stitched Equity Metrics
        # -----------------------------------------

        self.logger.info("--- Stitched Equity Metrics ---")

        for key, value in result.stitched_equity_metrics.items():
            self.logger.info(f"{key}={value}")

        # -----------------------------------------
        # Per-window Summary
        # -----------------------------------------

        self.logger.info("--- Per Window Summary ---")

        for window in result.windows:

            self.logger.info(
                f"Window="
                f"{window.window_index:02d} | "
                f"Trades={window.trade_count} | "
                f"Expectancy="
                f"{window.test_metrics.get('expectancy_pct')} | "
                f"DD="
                f"{window.test_metrics.get('max_drawdown_pct')} | "
                f"OptStability="
                f"{window.optimization_stability_score} | "
                f"Params={window.best_params}"
            )

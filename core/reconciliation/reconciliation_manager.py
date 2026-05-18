from typing import Optional

from core.entities.position import Position
from core.entities.broker_position import BrokerPosition
from core.logging.logger import get_logger


class ReconciliationManager:
    """
    Compares runtime state against broker state.

    Future responsibilities:
    - restart recovery
    - broker/runtime sync validation
    - orphan position detection
    - live runtime reconciliation
    """

    def __init__(self):
        self.logger = get_logger(__name__)

    def compare_positions(
        self,
        runtime_position: Optional[Position],
        broker_positions: list[BrokerPosition],
    ) -> bool:
        """
        MVP reconciliation check.
        """

        if runtime_position is None and not broker_positions:

            self.logger.info("RECONCILIATION OK | No runtime or broker positions")

            return True

        if runtime_position is not None and not broker_positions:

            self.logger.warning(
                "RECONCILIATION MISMATCH | "
                "Runtime position exists but broker has none"
            )

            return False

        if runtime_position is None and broker_positions:

            self.logger.warning(
                "RECONCILIATION MISMATCH | "
                "Broker positions exist but runtime has none"
            )

            return False

        self.logger.info("RECONCILIATION PARTIAL CHECK PASSED")

        return True

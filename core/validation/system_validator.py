from core.config.app_config import AppConfig
from core.broker.base_broker import BaseBroker
from core.risk.live_risk_guard import LiveRiskGuard
from core.risk.kill_switch import KillSwitch
from core.state.state_store import StateStore
from core.logging.logger import get_logger

logger = get_logger(__name__)


class SystemValidator:
    """
    Final system validation before trading.
    """

    def __init__(
        self,
        config: AppConfig,
        broker: BaseBroker,
        state_store: StateStore,
        kill_switch: KillSwitch,
    ):
        self.config = config
        self.broker = broker
        self.state_store = state_store
        self.kill_switch = kill_switch

    def validate(self) -> bool:
        logger.info("Starting system validation")

        if not self._validate_config():
            return False
        if not self._validate_broker():
            return False
        if not self._validate_state():
            return False
        if not self._validate_kill_switch():
            return False

        logger.info("System validation PASSED")
        return True

    def _validate_config(self) -> bool:
        if self.config.initial_capital <= 0:
            logger.error("Invalid initial capital")
            return False

        if self.config.risk_per_trade_pct <= 0:
            logger.error("Invalid risk per trade")
            return False

        return True

    def _validate_broker(self) -> bool:
        try:
            balance = self.broker.get_account_balance()
            logger.info(f"Broker balance: {balance}")
        except Exception as e:
            logger.error("Broker connectivity failed", extra={"error": str(e)})
            return False

        return balance > 0

    def _validate_state(self) -> bool:
        state = self.state_store.load()
        if state.get("open_position"):
            logger.warning("Open position exists in persisted state")
        return True

    def _validate_kill_switch(self) -> bool:
        if self.kill_switch.is_active():
            logger.critical(
                "Kill switch ACTIVE",
                extra={"reason": self.kill_switch.reason()},
            )
            return False
        return True

from typing import Optional

from core.broker.base_broker import BaseBroker
from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig


class SessionManager:
    """
    Single entry point for broker sessions.
    Ensures login happens once per run.
    """

    def __init__(
        self,
        broker_name: str,
        config,
        paper_mode: bool = True,
        enable_historical: bool = True,
    ):
        self.broker_name = broker_name
        self.config = config
        self.paper_mode = paper_mode
        self.enable_historical = enable_historical

        self._broker: Optional[BaseBroker] = None

    def get_broker(self) -> BaseBroker:
        """
        Returns a logged-in broker instance.
        """
        if self._broker is not None:
            return self._broker

        if self.broker_name == "ANGELONE":
            broker = AngelOneBroker(
                config=self.config,
                paper_mode=self.paper_mode,
                enable_historical_api=self.enable_historical,
            )
        else:
            raise ValueError(f"Unsupported broker: {self.broker_name}")

        broker.login()   # 🔐 happens ONCE
        self._broker = broker
        return broker

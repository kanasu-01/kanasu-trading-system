from core.broker.base_broker import BaseBroker
from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import (
    AngelOneConfig,
)


def create_angelone_broker(
    paper_mode: bool,
    enable_historical_api: bool,
) -> BaseBroker:

    config = AngelOneConfig.load_from_env()

    broker = AngelOneBroker(
        config=config,
        paper_mode=paper_mode,
        enable_historical_api=enable_historical_api,
    )

    broker.login()

    return broker
from enum import Enum


class RuntimeMode(Enum):
    BACKTEST = "BACKTEST"
    WALK_FORWARD = "WALK_FORWARD"
    PAPER = "PAPER"
    LIVE = "LIVE"

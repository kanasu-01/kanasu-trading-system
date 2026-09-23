from pydantic import BaseModel, ConfigDict, Field


class StrictApiModel(BaseModel):
    """Base model for stable API contracts."""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False,
    )


class ApiErrorResponse(StrictApiModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class MarketOption(StrictApiModel):
    id: str
    name: str


class SymbolOption(StrictApiModel):
    symbol: str
    exchange: str


class TimeframeOption(StrictApiModel):
    id: str
    label: str


class StrategyOption(StrictApiModel):
    id: str
    name: str

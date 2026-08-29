from pydantic import BaseModel


class PaperTradingStartRequest(BaseModel):

    symbol: str

    strategy_id: str

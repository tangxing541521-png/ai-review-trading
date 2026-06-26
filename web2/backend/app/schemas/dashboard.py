from pydantic import BaseModel


class DashboardResponse(BaseModel):
    market_status: str
    allow_trade: str
    risk_level: str
    position_advice: str
    total_assets: str
    daily_return: str
    cumulative_return: str
    one_sentence_summary: str
    membership_level: str
    disclaimer: str

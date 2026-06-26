from pydantic import BaseModel


class ReportResponse(BaseModel):
    title: str
    allowed: bool
    content: str
    membership_level: str
    disclaimer: str

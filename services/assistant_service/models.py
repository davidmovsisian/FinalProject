from pydantic import BaseModel, Field


class InsightRequest(BaseModel):
    query: str = Field(min_length=1)
    context: str = ""


class InsightResponse(BaseModel):
    insight: str

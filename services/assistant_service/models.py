from pydantic import BaseModel, Field
from typing import Any, List, Optional

class RoomCondition(BaseModel):
    type: str = Field(min_length=1)
    condition_score: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)

class PropertyListing(BaseModel):
    property_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    price: str = Field(min_length=1)
    overall_condition: str = Field(min_length=1)
    living_room: int = Field(ge=0)
    bed_rooms: int = Field(ge=0)
    kitchen: int = Field(ge=0)
    bath_rooms: int = Field(ge=0)
    storage: str = Field("")
    features: list[str] = Field(default_factory=list)
    conditions: list[RoomCondition] = Field(default_factory=list)

class SimilarListing(BaseModel):
    id: str
    distance: float
    listing: PropertyListing

class InsightRequest(BaseModel):
    listing: PropertyListing
    similar_listings: list[SimilarListing]

class HistoryMessage(BaseModel):
    role: str  
    content: Any = None

class ChatRequest(BaseModel):
    history: Optional[List[HistoryMessage]] = None
    message: Optional[str] = None

class ChatResponse(BaseModel):
    response: str


class ListingQuestionRequest(BaseModel):
    listing_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    # k: int | None = Field(default=5, ge=1)


class ListingQuestionResponse(BaseModel):
    response: str
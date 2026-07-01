from pydantic import BaseModel, Field

# MIN_DESCRIPTION_LENGTH = 2

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

class InsightResponse(BaseModel):
    listing_id: str
    similar_listings: list[SimilarListing]
    insight: str
    
class AddListingResponse(BaseModel):
    success: bool
    listing_id: str

class RetrieveRequest(BaseModel):
    listing_id: str
    k: int | None = Field(default=5)

class RetrieveResponse(BaseModel):
    listing: PropertyListing
    similar_listings: list[SimilarListing]
import json
from json import JSONDecodeError

from pydantic import BaseModel, Field, ValidationError


class PropertyListing(BaseModel):
    property_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    price: str = Field(min_length=1)
    rooms_number: int = Field(ge=0)
    features: list[str] = Field(default_factory=list)


class QueryRequest(BaseModel):
    description: str = Field(min_length=2)

    def to_listing(self) -> PropertyListing:
        try:
            payload = json.loads(self.description)
        except JSONDecodeError as exc:
            raise ValueError("description must be a valid JSON string") from exc

        try:
            return PropertyListing.model_validate(payload)
        except ValidationError as exc:
            raise ValueError("description JSON does not match required listing schema") from exc


class SimilarListing(BaseModel):
    id: str
    distance: float | None = None
    listing: PropertyListing


class QueryResponse(BaseModel):
    similar_listings: list[SimilarListing]
    insight: str

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from config import settings
from models import PropertyListing, InsightResponse, RetrieveRequest, RetrieveResponse
from rag_service import RAGService
import requests

rag_service = RAGService()

@asynccontextmanager
async def lifespan(_: FastAPI):
    rag_service.initialize()
    yield

app = FastAPI(title=settings.app_name, lifespan=lifespan)

@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "vector_count": rag_service.collection_size(),
    }

@app.post("/retrieve_by_id", response_model=RetrieveResponse)
def retrieve_by_id(request: RetrieveRequest) -> RetrieveResponse:
    similar_listings = rag_service.retrieve_listings_by_id(request.listing_id, k=request.k)
    return RetrieveResponse(similar_listings=similar_listings)

@app.post("/create-insight")
def create_insight(listing: PropertyListing) -> InsightResponse:
    print(f"Listing: {listing.model_dump()}")
    api_url = settings.create_insight_url.strip()
    if not api_url:
        raise HTTPException(status_code=503, detail="Create insight URL is not configured.")
    similar = rag_service.retrieve_listings(listing, k=settings.top_k)
    try:
        payload = {
            "listing": listing.model_dump(),
            "similar_listings": [s.model_dump() for s in similar],
        }
        print(f"Sending payload to assistant_service: {payload}")
        response = requests.post(api_url, json=payload, timeout=360)
        response.raise_for_status()
        insight = response.json().get("insight", "")
    except requests.RequestException as e:
        insight = f"Error communicating with assistant_service: {e}"

    listing_id = rag_service.add_listing(listing)
    return InsightResponse(listing_id=listing_id, similar_listings=similar, insight=insight)
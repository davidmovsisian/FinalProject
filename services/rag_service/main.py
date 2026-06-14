from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from config import settings
from models import AddListingResponse, InsightRequest, RetrieveResponse
from rag_service import RAGService

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

@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve_endpoint(request: InsightRequest) -> RetrieveResponse:
    try:
        listing = request.to_listing()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    similar = rag_service.retrieve(listing, k=settings.top_k)
    return RetrieveResponse(similar_listings=similar)


@app.post("/add", response_model=AddListingResponse)
def add_listing_endpoint(request: InsightRequest) -> AddListingResponse:
    try:
        listing = request.to_listing()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    listing_id = rag_service.add_vector_store(listing)
    return AddListingResponse(success=True, listing_id=listing_id)


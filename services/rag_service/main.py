from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from config import settings
from models import InsightRequest, InsightResponse
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
        "llm_available": rag_service.llm_available,
        "llm_error": rag_service.llm_error,
        "vector_count": rag_service.collection_size(),
    }

@app.post("/create-insight", response_model=InsightResponse)
def create_insight_endpoint(request: InsightRequest) -> InsightResponse:
    try:
        listing = request.to_listing()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    similar = rag_service.retrieve(listing, k=settings.top_k)
    insight = rag_service.generate_insight(listing, similar)
    rag_service.add_listing_vector_store(listing)
    return InsightResponse(similar_listings=similar, insight=insight)

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from assistant_service import AssistantService
from config import settings
from models import InsightRequest, InsightResponse

assistant_service = AssistantService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    assistant_service.initialize()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "llm_available": assistant_service.llm_available,
        "llm_error": assistant_service.llm_error,
    }


@app.post("/generate-insight", response_model=InsightResponse)
def generate_insight_endpoint(request: InsightRequest) -> InsightResponse:
    if not request.query.strip():
        raise HTTPException(status_code=422, detail="query must not be blank")

    insight = assistant_service.generate_insight(
        query=request.query,
        context=request.context,
    )
    return InsightResponse(insight=insight)

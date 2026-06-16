from contextlib import asynccontextmanager

from fastapi import FastAPI

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
    insight = assistant_service.generate_insight(
        query=request.query,
        context=request.context,
    )
    return InsightResponse(insight=insight)

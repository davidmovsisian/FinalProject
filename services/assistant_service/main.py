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


@app.post("/general_answer", response_model=InsightResponse)
def general_answer(request: InsightRequest) -> InsightResponse:
    insight = assistant_service.general_answer(
        query=request.query
    )
    return InsightResponse(insight=insight)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from assistant_service import AssistantService
from config import settings
from pydantic import BaseModel
from typing import List, Optional

assistant_service = AssistantService()

class HistoryMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    history: Optional[List[HistoryMessage]] = None
    message: str

class ChatResponse(BaseModel):
    response: str

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

@app.post("/general_answer", response_model=ChatResponse)
def general_answer(request: ChatRequest) -> ChatResponse:
    history =[msg.model_dump() for msg in (request.history or [])]
    answer = assistant_service.general_answer(
        message=request.message,
        history=history,
    )
    return ChatResponse(response=answer)

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from assistant_service import AssistantService
from config import settings
from pydantic import BaseModel, Field
from typing import Any, List, Optional

from services.rag_service.models import SimilarListing

assistant_service = AssistantService()

class RoomCondition(BaseModel):
    type: str = Field(min_length=1)
    condition_score: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0, le=1)
    
class PropertyListing(BaseModel):
    property_type: str = Field(min_length=1)
    location: str = Field(min_length=1)
    price: str = Field(min_length=1)
    rooms_number: int = Field(ge=0)
    features: list[str] = Field(default_factory=list)
    conditions: list[RoomCondition] = Field(default_factory=list)
    
def _to_str(content: Any) -> str:
    """Normalize Gradio content to a plain string.
    Gradio 6 can send content as a string or as a list of content blocks
    (multimodal format). Extract text from whichever form arrives.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return str(content) if content is not None else ""


class HistoryMessage(BaseModel):
    role: str            # "user" or "assistant"
    content: Any = None  # str normally; list of blocks in Gradio 6 multimodal


class ChatRequest(BaseModel):
    history: Optional[List[HistoryMessage]] = None
    message: Optional[str] = None


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
    # Normalize every history entry's content to a plain string and drop empties
    history = [
        {"role": msg.role, "content": _to_str(msg.content)}
        for msg in (request.history or [])
        if msg.role in ("user", "assistant") and msg.content
    ]
    print(
        f"Received request: message={request.message}, "
        f"history=[{', '.join([h['role'] + ':' + h['content'][:40] for h in history])}]"
    )
    answer = assistant_service.general_answer(
        message=request.message,
        history=history,
    )
    return ChatResponse(response=answer)

@app.post("/create-insight")
def create_insight(listing: PropertyListing, context: List[SimilarListing]) -> str:
    
    insight = assistant_service.generate_insight(listing, context= [item.model_dump() for item in context])
    return insight
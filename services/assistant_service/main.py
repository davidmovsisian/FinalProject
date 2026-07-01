from contextlib import asynccontextmanager
from fastapi import FastAPI
from assistant_service import AssistantService
from config import settings
from typing import Any
from models import (
    ChatRequest,
    ChatResponse,
    InsightRequest,
    ListingQuestionRequest,
    ListingQuestionResponse,
)

assistant_service = AssistantService()

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
        "gemini_available": assistant_service.gemini_available,
        "gemini_error": assistant_service.gemini_error,
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
def create_insight(request: InsightRequest) -> dict:
    insight = assistant_service.generate_insight(request.listing, request.similar_listings)
    return {"insight": insight}


@app.post("/answer-with-listing", response_model=ListingQuestionResponse)
def answer_with_listing(request: ListingQuestionRequest) -> ListingQuestionResponse:
    answer = assistant_service.answer_with_listing_context(
        question=request.question,
        listing_id=request.listing_id
    )
    return ListingQuestionResponse(response=answer)

@app.post("/residential")
def residential(request: InsightRequest) -> dict:
    return {"residential": "ok"}

@app.post("/commercial")
def commercial(request: InsightRequest) -> dict:
    return {"commercial": "ok"}
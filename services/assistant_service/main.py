from contextlib import asynccontextmanager

from fastapi import FastAPI

from assistant_service import AssistantService
from config import settings
from models import InsightRequest, InsightResponse

assistant_service = AssistantService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    assistant_service.initialize()
    
    # from llama_cpp import Llama

    # try:
    #     llm = Llama(
    #         model_path="/models/Dolphin3.0-Llama3.1-8B-Q4_K_M.gguf",
    #         n_ctx=12288,
    #         verbose=False,
    #     )

    #     print("LLM initialized successfully.")
    #     response = llm.create_chat_completion(
    #         messages=[
    #             {
    #                 "role": "system",
    #                 "content": "You are a helpful Real Estate Assistant."
    #             },
    #             {
    #                 "role": "user",
    #                 "content": "What factors affect property valuation?"
    #             }
    #         ],
    #         max_tokens=100,
    #         temperature=0,
    #     )

    #     print("LLM response:", response)
    #     print("LLM response content:", response["choices"][0]["message"]["content"])
    # except Exception as e:
    #     print("Error initializing LLM:", e)

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

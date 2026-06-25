from pathlib import Path
from llama_cpp import Llama
from config import settings
from models import PropertyListing, SimilarListing
from utils import listing_to_text

class AssistantService:
    def __init__(self) -> None:
        self._llm = None
        self._llm_error: str | None = None

    @property
    def llm_available(self) -> bool:
        return self._llm is not None

    @property
    def llm_error(self) -> str | None:
        return self._llm_error

    def initialize(self) -> None:
        if settings.assistant_llm_model_path:
            model_path = Path(settings.assistant_llm_model_path)
            if model_path.exists():
                try:
                    self._llm = Llama(
                        model_path=str(model_path),
                        temperature=settings.llm_temperature,
                        max_tokens=settings.llm_max_tokens,
                        n_ctx=settings.llm_n_ctx,
                        verbose=False,
                    )
                except Exception as exc:
                    self._llm_error = (
                        "Could not initialize LlamaCpp model. "
                        f"Path: {model_path}. Error: {exc}"
                    )
            else:
                self._llm_error = f"GGUF model file not found at: {model_path}"
        else:
            self._llm_error = "ASSISTANT_LLM_MODEL_PATH is not set"

    def general_answer(self, message: str, history: list[dict] | None = None) -> str:
        SYSTEM_PROMPT = """
            You are a knowledgeable and professional Real Estate Assistant.

            Answer questions related to:

            - property valuation
            - residential and commercial real estate
            - inspections
            -certifications
            - mortgages
            - rentals
            - investments
            - zoning
            - sustainability
            -construction quality
            -property maintenance

            If the question is unrelated to real estate,
            reply exactly:

            Please ask a real-estate-related question.

            Keep answers concise (2-4 sentences).
            """
        if not self._llm:
            return (
                "LLM generation is unavailable. "
                f"Reason: {self._llm_error or 'unknown error'}."
            )
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            for turn in history:
                role = turn.get("role", "")
                content = turn.get("content", "")
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        print(f"Generating answer for message: {message}")
        print(f"With history: {history}")
        response = self._llm.create_chat_completion(messages=messages)

        answer = response["choices"][0]["message"]["content"]
        print(f"Generated answer: {answer}")
        
        return answer
    
    def generate_insight(self, query_listing: PropertyListing, similar_listings: list[SimilarListing]) -> str:
        if not similar_listings:
            return "No similar listings were found, so no grounded insight can be generated."

        if not self._llm:
            return "LLM generation is unavailable."

        SYSTEM_PROMPT = """
            You are a knowledgeable and professional Real Estate Assistant.
            Use only the provided similar listings context to produce a concise insight.
            Do not fabricate facts. If context is insufficient, explicitly say so.
            Keep insight concise (2-4 sentences).
            """

        context = "\n".join(
            f"- {item.id}: {listing_to_text(item.listing)} (distance={item.distance:.4f})"
            for item in similar_listings
        )

        user_message = (
            f"Input listing:\n{listing_to_text(query_listing)}\n\n"
            f"Similar listings:\n{context}"
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        print(f"Generating insight for listing: {query_listing}")
        print(f"With similar listings: {[item.id for item in similar_listings]}")
        response = self._llm.create_chat_completion(messages=messages)

        insight = response["choices"][0]["message"]["content"]
        print(f"Generated insight: {insight}")

        return insight.strip()

    def collection_size(self) -> int:
        try:
            return len(self._vectorstore.get()["ids"])
        except Exception:
            return 0
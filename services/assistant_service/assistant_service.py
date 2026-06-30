from pathlib import Path
from llama_cpp import Llama
import requests
import google.generativeai as genai
from config import settings
from models import PropertyListing, SimilarListing
from utils import listing_to_text

class AssistantService:
    def __init__(self) -> None:
        self._llm = None
        self._llm_error: str | None = None
        self._gemini_model = None
        self._gemini_error: str | None = None

    @property
    def llm_available(self) -> bool:
        return self._llm is not None

    @property
    def llm_error(self) -> str | None:
        return self._llm_error

    @property
    def gemini_available(self) -> bool:
        return self._gemini_model is not None

    @property
    def gemini_error(self) -> str | None:
        return self._gemini_error

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

        if settings.gemini_api_key:
            try:
                genai.configure(api_key=settings.gemini_api_key)
                self._gemini_model = genai.GenerativeModel(settings.gemini_model)
            except Exception as exc:
                self._gemini_error = f"Could not initialize Gemini model: {exc}"
        else:
            self._gemini_error = "GEMINI_API_KEY is not set"

    def _retrieve_similar_listings_by_id(self, listing_id: str, k: int | None) -> list[SimilarListing]:
        api_url = settings.rag_retrieve_by_id_url.strip()

        payload = {
            "listing_id": listing_id,
            "k": k or settings.gemini_max_context_items,
        }
        response = requests.post(api_url, json=payload, timeout=settings.rag_request_timeout)
        response.raise_for_status()

        data = response.json()
        raw_list = data.get("similar_listings", [])
        similar_listings: list[SimilarListing] = []
        for item in raw_list:
            similar_listings.append(SimilarListing.model_validate(item))
        return similar_listings

    def answer_with_listing_context(
        self,
        question: str,
        listing_id: str,
        k: int | None = None,
    ) -> str:
        try:
            similar_listings = self._retrieve_similar_listings_by_id(listing_id=listing_id, k=k)
        except Exception as exc:
            return f"Could not retrieve similar listings: {exc}"

        context = "\n".join(
            f"- {item.id}: {listing_to_text(item.listing)} (distance={item.distance:.4f})"
            for item in similar_listings
        )

        prompt = (
            "You are a professional real-estate assistant. Use only the context below to answer "
            "the user's question. If the context is insufficient, clearly say that. "
            "If the question is unrelated to real estate, reply exactly: 'Please ask a real-estate-related question.' "
            "Keep the answer concise (2-5 sentences).\n\n"
            f"Listing ID: {listing_id}\n\n"
            f"User Question:\n{question}\n\n"
            f"Similar Listings Context:\n{context}"
        )

        try:
            response = self._gemini_model.generate_content(prompt)
            answer = (response.text or "").strip()
            if not answer:
                answer = "Gemini returned an empty response."
            return answer   
        except Exception as exc:
            return f"Could not generate Gemini answer: {exc}"

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
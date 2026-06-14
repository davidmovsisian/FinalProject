from pathlib import Path

from langchain_core.prompts import PromptTemplate
from langchain_community.llms import LlamaCpp

from config import settings
from utils import format_context


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
        self._llm = None
        self._llm_error = None

        if settings.assistant_llm_model_path:
            model_path = Path(settings.assistant_llm_model_path)
            if model_path.exists():
                try:
                    self._llm = LlamaCpp(
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

    def generate_insight(self, query: str, context: str = "") -> str:
        if not self._llm:
            return (
                "LLM generation is unavailable. "
                f"Reason: {self._llm_error or 'unknown error'}."
            )

        prompt = PromptTemplate.from_template(
            """
You are a real-estate assistant.
Use only the provided similar listings context to produce a concise insight.
Do not fabricate facts. If context is insufficient, explicitly say so.
Always cite the listing IDs that informed your insight.

User query:
{query}

Similar listings:
{context}

Return 2-4 sentences.
""".strip()
        )

        response = self._llm.invoke(
            prompt.format(query=query.strip(), context=format_context(context))
        )
        return str(response).strip()

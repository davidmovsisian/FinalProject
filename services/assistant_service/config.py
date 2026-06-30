import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "Assistant Service")
        self.app_host = os.getenv("APP_HOST", "0.0.0.0")
        self.app_port = int(os.getenv("APP_PORT", "8001"))

        self.assistant_llm_model_path = os.getenv("ASSISTANT_LLM_MODEL_PATH")
        self.llm_n_ctx = int(os.getenv("LLM_N_CTX", "4096"))
        self.llm_temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))
        self.llm_max_tokens = int(os.getenv("LLM_MAX_TOKENS", "512"))

        self.rag_retrieve_by_id_url = os.getenv(
            "RAG_RETRIEVE_BY_ID_URL",
            "http://rag_service:8000/retrieve_by_id",
        )
        self.rag_request_timeout = int(os.getenv("RAG_REQUEST_TIMEOUT", "60"))

        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.gemini_max_context_items = int(os.getenv("GEMINI_MAX_CONTEXT_ITEMS", "5"))


settings = Settings()

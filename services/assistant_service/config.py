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


settings = Settings()

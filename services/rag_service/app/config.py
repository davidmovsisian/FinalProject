from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RAG Service"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    chroma_path: str = "./chroma_db"
    chroma_collection: str = "property_listings"

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    llm_model_path: str | None = Field(default=None, validation_alias="RAG_LLM_MODEL_PATH")
    llm_n_ctx: int = 2048
    llm_temperature: float = 0.2
    llm_max_tokens: int = 256

    top_k: int = Field(default=3, ge=1, le=10)

    def chroma_dir(self) -> Path:
        return Path(self.chroma_path)


settings = Settings()

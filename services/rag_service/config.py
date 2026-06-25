import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self) -> None:
        self.app_name = os.getenv("APP_NAME", "RAG Service")
        self.app_host = os.getenv("APP_HOST", "0.0.0.0")
        self.app_port = int(os.getenv("APP_PORT", "8000"))

        self.chroma_path = os.getenv("CHROMA_PATH", "./chroma_db")
        self.listings_collection = os.getenv("LISTINGS_COLLECTION")
        
        self.embedding_model = os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.embedding_model_path = os.getenv("RAG_EMBEDDING_MODEL_PATH")

        self.top_k = int(os.getenv("TOP_K", "3"))

        self.create_insight_url = os.getenv("CREATE_INSIGHT_URL", "http://assistant_service:8000/create-insight")

    def chroma_dir(self) -> Path:
        return Path(self.chroma_path)


settings = Settings()

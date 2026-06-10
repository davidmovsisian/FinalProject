from pathlib import Path

from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import LlamaCpp
from langchain_community.vectorstores import Chroma

from config import settings
from data import SEED_LISTINGS
from models import PropertyListing, SimilarListing
from utils import listing_to_text


class RAGService:
    def __init__(self) -> None:
        print("start __init__ RAGService...")
        self._llm_error: str | None = None
        embedding_source = settings.embedding_model_path or settings.embedding_model
        self._embedding = HuggingFaceEmbeddings(
            model_name=embedding_source,
            model_kwargs={"local_files_only": bool(settings.embedding_model_path)},
        )
        self._vectorstore = Chroma(
            collection_name=settings.listings_collection,
            embedding_function=self._embedding,
            persist_directory=str(settings.chroma_dir()),
        )
        self._llm = None
        print("end __init__ RAGService...")

    @property
    def llm_available(self) -> bool:
        return self._llm is not None

    @property
    def llm_error(self) -> str | None:
        return self._llm_error

    def initialize(self) -> None:
        settings.chroma_dir().mkdir(parents=True, exist_ok=True)
        if self.collection_size() == 0:
            self.seed_vector_store()

        self._llm = None
        self._llm_error = None

        if settings.llm_model_path:
            model_path = Path(settings.llm_model_path)
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
            self._llm_error = "RAG_LLM_MODEL_PATH is not set"

    def seed_vector_store(self) -> int:
        texts = []
        metadatas = []

        for item in SEED_LISTINGS:
            listing = PropertyListing(
                property_type=item["property_type"],
                location=item["location"],
                price=item["price"],
                rooms_number=item["rooms_number"],
                features=item["features"],
            )
            texts.append(listing_to_text(listing))
            metadatas.append(
                {
                    "id": f"listing-{self._vectorstore.collection_size() + 1}",
                    "property_type": listing.property_type,
                    "location": listing.location,
                    "price": listing.price,
                    "rooms_number": listing.rooms_number,
                    "features": ", ".join(listing.features),
                }
            )
        self._vectorstore.add_texts(texts=texts, metadatas=metadatas)
        self._vectorstore.persist()
        return self._vectorstore.collection_size()

    def add_vector_store(self, listing: PropertyListing) -> None:
        text = listing_to_text(listing)
        listing_id = f"listing-{self._vectorstore.collection_size() + 1}"
        metadata = {
            "id": listing_id,
            "property_type": listing.property_type,
            "location": listing.location,
            "price": listing.price,
            "rooms_number": listing.rooms_number,
            "features": ", ".join(listing.features),
        }
        self._vectorstore.add_texts(texts=[text], metadatas=[metadata], ids=[listing_id])
        self._vectorstore.persist()
        
    def retrieve(self, listing: PropertyListing, k: int | None = None) -> list[SimilarListing]:
        results = self._vectorstore.similarity_search_with_score(
            query=listing_to_text(listing),
            k=k or settings.top_k,
        )

        similar: list[SimilarListing] = []
        for index, (document, distance) in enumerate(results, start=1):
            metadata = document.metadata or {}
            features = metadata.get("features", "")
            doc_id = metadata.get("id")
            if not doc_id:
                doc_id = f"retrieved-{index}"
            similar.append(
                SimilarListing(
                    id=doc_id,
                    distance=float(distance),
                    listing=PropertyListing(
                        property_type=str(metadata.get("property_type", "unknown")),
                        location=str(metadata.get("location", "unknown")),
                        price=str(metadata.get("price", "unknown")),
                        rooms_number=int(metadata.get("rooms_number", 0)),
                        features=[part.strip() for part in str(features).split(",") if part.strip()],
                    ),
                )
            )

        return similar

    def generate_insight(self, query_listing: PropertyListing, similar_listings: list[SimilarListing]) -> str:
        if not similar_listings:
            return "No similar listings were found, so no grounded insight can be generated."

        if not self._llm:
            listing_ids = ", ".join(item.id for item in similar_listings)
            return (
                "LLM generation is unavailable. "
                f"Reason: {self._llm_error or 'unknown error'}. "
                f"Retrieved similar listings: {listing_ids}."
            )

        context = "\n".join(
            f"- {item.id}: {listing_to_text(item.listing)} (distance={item.distance:.4f})"
            for item in similar_listings
        )

        prompt = PromptTemplate.from_template(
            """
You are a real-estate assistant.
Use only the provided similar listings context to produce a concise insight.
Do not fabricate facts. If context is insufficient, explicitly say so.
Always cite the listing IDs that informed your insight.

Input listing:
{input_listing}

Similar listings:
{context}

Return 2-4 sentences.
""".strip()
        )

        response = self._llm.invoke(
            prompt.format(input_listing=listing_to_text(query_listing), context=context)
        )
        return str(response).strip()

    def collection_size(self) -> int:
        try:
            return len(self._vectorstore.get()["ids"])
        except Exception:
            return 0

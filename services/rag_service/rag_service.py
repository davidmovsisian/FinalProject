import json
import re
from pathlib import Path
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from config import settings
from models import PropertyListing, SimilarListing
from utils import listing_to_text, parse_conditions

class RAGService:
    def __init__(self) -> None:
        print("start __init__ RAGService...")
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
        print("end __init__ RAGService...")

    def initialize(self) -> None:
        settings.chroma_dir().mkdir(parents=True, exist_ok=True)
        if self.collection_size() == 0:
            self.seed_vector_store()

    def _load_seed_listings(self) -> list[dict]:
        data_file = Path(__file__).resolve().parent / "data.json"
        raw_text = data_file.read_text(encoding="utf-8")

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Be tolerant of trailing commas in the seed file.
            sanitized = re.sub(r",\s*([\]}])", r"\1", raw_text)
            return json.loads(sanitized)

    def seed_vector_store(self) -> int:
        texts = []
        metadatas = []

        for index, item in enumerate(self._load_seed_listings(), start=1):
            listing = PropertyListing(
                property_type=item["property_type"],
                location=item["location"],
                price=item["price"],
                rooms_number=item["rooms_number"],
                features=item["features"],
                conditions=item.get("conditions", []),
            )
            text = listing_to_text(listing)
            texts.append(text)
            metadatas.append(
                {
                    "id": f"listing-{index}",
                    "property_type": listing.property_type,
                    "location": listing.location,
                    "price": listing.price,
                    "rooms_number": listing.rooms_number,
                    "features": ", ".join(listing.features),
                    "conditions": json.dumps([condition.model_dump() for condition in listing.conditions]),
                }
            )
        ids = [metadata["id"] for metadata in metadatas]
        self._vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        self._vectorstore.persist()
        return self._vectorstore.collection_size()

    def add_listing(self, listing: PropertyListing) -> str:
        text = listing_to_text(listing)
        listing_id = f"listing-{self._vectorstore.collection_size() + 1}"
        metadata = {
            "id": listing_id,
            "property_type": listing.property_type,
            "location": listing.location,
            "price": listing.price,
            "rooms_number": listing.rooms_number,
            "features": ", ".join(listing.features),
            "conditions": json.dumps([condition.model_dump() for condition in listing.conditions]),
        }
        self._vectorstore.add_texts(texts=[text], metadatas=[metadata], ids=[listing_id])
        self._vectorstore.persist()
        return listing_id
        
    def retrieve_listings(self, listing: PropertyListing, k: int | None = None) -> list[SimilarListing]:
        results = self._vectorstore.similarity_search_with_score(
            query=listing_to_text(listing),
            k=k or settings.top_k,
        )

        similar: list[SimilarListing] = []
        for index, (document, distance) in enumerate(results, start=1):
            metadata = document.metadata or {}
            features = metadata.get("features", "")
            conditions = parse_conditions(metadata.get("conditions", []))
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
                        conditions=conditions,
                    ),
                )
            )

        return similar

    def collection_size(self) -> int:
        try:
            return len(self._vectorstore.get()["ids"])
        except Exception:
            return 0

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
        if settings.seed_vs:
            print("seed_vs=True: clearing vector store and re-seeding...")
            self.clear_vector_store()
            self.seed_vector_store()
        elif self.collection_size() == 0:
            self.seed_vector_store()

    def clear_vector_store(self) -> None:
        existing_ids = self._vectorstore.get()["ids"]
        if existing_ids:
            self._vectorstore.delete(ids=existing_ids)
            self._vectorstore.persist()
            print(f"Deleted {len(existing_ids)} documents from vector store.")

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
                overall_condition=item["overall_condition"],
                living_room=item["living_room"],
                bed_rooms=item["bed_rooms"],
                kitchen=item["kitchen"],
                bath_rooms=item["bath_rooms"],
                storage=item["storage"],
                features=item.get("features", []),
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
                    "overall_condition": listing.overall_condition,
                    "living_room": listing.living_room,
                    "bed_rooms": listing.bed_rooms,
                    "kitchen": listing.kitchen,
                    "bath_rooms": listing.bath_rooms,
                    "storage": listing.storage,
                    "features": ", ".join(listing.features),
                    "conditions": json.dumps([condition.model_dump() for condition in listing.conditions]),
                }
            )
        ids = [metadata["id"] for metadata in metadatas]
        self._vectorstore.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        self._vectorstore.persist()
        print(f"Seeded vector store with {len(texts)} listings.")
        return self.collection_size()

    def add_listing(self, listing: PropertyListing) -> str:
        text = listing_to_text(listing)
        listing_id = f"listing-{self.collection_size() + 1}"
        metadata = {
            "id": listing_id,
            "property_type": listing.property_type,
            "location": listing.location,
            "price": listing.price,
            "overall_condition": listing.overall_condition,
            "living_room": listing.living_room,
            "bed_rooms": listing.bed_rooms,
            "kitchen": listing.kitchen,
            "bath_rooms": listing.bath_rooms,
            "storage": listing.storage,
            "features": ", ".join(listing.features),
            "conditions": json.dumps([condition.model_dump() for condition in listing.conditions]),
        }
        self._vectorstore.add_texts(texts=[text], metadatas=[metadata], ids=[listing_id])
        self._vectorstore.persist()
        print(f"Added listing {listing_id} to vector store.")
        return listing_id

    def retrieve_listings_by_id(self, listing_id: str, k: int | None = None) -> tuple[PropertyListing, list[SimilarListing]]:
        # Retrieve the document by ID to get its text for similarity search
        print(f"looking up for similar lisings for listing_id {listing_id}")
        doc = self._vectorstore.get(ids=[listing_id])
        if not doc or not doc.get("documents"):
            print(f"No document found with ID: {listing_id}")
            return None, []

        query_text = doc["documents"][0]
        if not query_text:
            print(f"Document text is empty for ID: {listing_id}")
            return None, []

        # Build the queried listing from its stored metadata
        source_metadata = (doc.get("metadatas") or [{}])[0]
        source_features = source_metadata.get("features", "")
        source_conditions = parse_conditions(source_metadata.get("conditions", []))
        queried_listing = PropertyListing(
            property_type=str(source_metadata.get("property_type", "unknown")),
            location=str(source_metadata.get("location", "unknown")),
            price=str(source_metadata.get("price", "unknown")),
            overall_condition=str(source_metadata.get("overall_condition", "unknown")),
            living_room=int(source_metadata.get("living_room", 0)),
            bed_rooms=int(source_metadata.get("bed_rooms", 0)),
            kitchen=int(source_metadata.get("kitchen", 0)),
            bath_rooms=int(source_metadata.get("bath_rooms", 0)),
            storage=str(source_metadata.get("storage", "no")),
            features=[part.strip() for part in str(source_features).split(",") if part.strip()],
            conditions=source_conditions,
        )

        requested_k = k or settings.top_k
        results = self._vectorstore.similarity_search_with_score(
            query=query_text,
            k=requested_k + 1,
        )

        similar: list[SimilarListing] = []
        for index, (document, distance) in enumerate(results, start=1):
            metadata = document.metadata or {}
            features = metadata.get("features", "")
            conditions = parse_conditions(metadata.get("conditions", []))
            doc_id = metadata.get("id")
            if not doc_id:
                doc_id = f"retrieved-{index}"
            if doc_id == listing_id:
                continue
            similar.append(
                SimilarListing(
                    id=doc_id,
                    distance=float(distance),
                    listing=PropertyListing(
                        property_type=str(metadata.get("property_type", "unknown")),
                        location=str(metadata.get("location", "unknown")),
                        price=str(metadata.get("price", "unknown")),
                        overall_condition=str(metadata.get("overall_condition", "unknown")),
                        living_room=int(metadata.get("living_room", 0)),
                        bed_rooms=int(metadata.get("bed_rooms", 0)),
                        kitchen=int(metadata.get("kitchen", 0)),
                        bath_rooms=int(metadata.get("bath_rooms", 0)),
                        storage=str(metadata.get("storage", "no")),
                        features=[part.strip() for part in str(features).split(",") if part.strip()],
                        conditions=conditions,
                    ),
                )
            )
            if len(similar) >= requested_k:
                break
            print(f"similar listings: {json.dumps([sl.model_dump() for sl in similar])}")
        return queried_listing, similar
    
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
                        overall_condition=str(metadata.get("overall_condition", "unknown")),
                        living_room=int(metadata.get("living_room", 0)),
                        bed_rooms=int(metadata.get("bed_rooms", 0)),
                        kitchen=int(metadata.get("kitchen", 0)),
                        bath_rooms=int(metadata.get("bath_rooms", 0)),
                        storage=str(metadata.get("storage", "no")),
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
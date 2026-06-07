from .rag_service import RAGService


def main() -> None:
    service = RAGService()
    service.initialize()
    print(f"Current ChromaDB listing count: {service.collection_size()}")


if __name__ == "__main__":
    main()

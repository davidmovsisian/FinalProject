# RAG Service (Service 1)

FastAPI microservice for property-listing vector storage and similarity retrieval using ChromaDB.

## Endpoints

### `GET /health`
Returns service status and current vector collection size.

### `POST /retrieve`
Retrieve similar listings from the vector store.

Request:
```json
{
  "description": "{\"property_type\":\"apartment\",\"location\":\"Yerevan\",\"price\":\"$100000\",\"rooms_number\":2,\"features\":[\"balcony\",\"renovated\"]}"
}
```

Response:
```json
{
  "similar_listings": [
    {
      "id": "listing-1",
      "distance": 0.1023,
      "listing": {
        "property_type": "apartment",
        "location": "Yerevan, Kentron",
        "price": "$120000",
        "rooms_number": 2,
        "features": ["renovated", "balcony", "city view"],
        "conditions": []
      }
    }
  ]
}
```

### `POST /add`
Add a listing to the vector store.

Request:
```json
{
  "description": "{\"property_type\":\"apartment\",\"location\":\"Yerevan\",\"price\":\"$100000\",\"rooms_number\":2,\"features\":[\"balcony\",\"renovated\"]}"
}
```

Response:
```json
{
  "success": true,
  "listing_id": "listing-101"
}
```

## Setup
```bash
cd services/rag_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run service
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

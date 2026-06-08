# RAG Service (Service 1)

FastAPI microservice for property-listing similarity retrieval and insight generation.

## Request format
```json
{
  "description": "{\"property_type\":\"apartment\",\"location\":\"Yerevan\",\"price\":\"$100000\",\"rooms_number\":2,\"features\":[\"balcony\",\"renovated\"]}"
}
```

## Response format
```json
{
  "similar_listings": [
    {
      "id": "listing-001",
      "distance": 0.1023,
      "listing": {
        "property_type": "apartment",
        "location": "Yerevan, Kentron",
        "price": "$120000",
        "rooms_number": 2,
        "features": ["renovated", "balcony", "city view"]
      }
    }
  ],
  "insight": "..."
}
```

## Setup
```bash
cd /tmp/workspace/davidmovsisian/FinalProject/services/rag_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run service
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

If `RAG_LLM_MODEL_PATH` is missing or invalid, the service still returns retrieved listings and an explicit fallback message in `insight`.

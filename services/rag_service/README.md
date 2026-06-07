# RAG Service (Service 1)

FastAPI microservice for property-listing similarity retrieval and grounded insight generation.

## Features
- `POST /query` endpoint that accepts `description` as a JSON string
- Input validation for malformed JSON and schema errors
- Embedding with HuggingFace sentence-transformer model
- Persistent ChromaDB vector store with startup seeding
- Top-3 similar listings retrieval
- LangChain prompt + llama.cpp generation through `llama-cpp-python`
- `GET /health` endpoint

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

## Seed database
```bash
python -m app.seed
```

## Run service
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Example query
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "description": "{\"property_type\":\"apartment\",\"location\":\"Yerevan, Arabkir\",\"price\":\"$110000\",\"rooms_number\":3,\"features\":[\"renovated\",\"parking\"]}"
  }'
```

If `RAG_LLM_MODEL_PATH` is missing or invalid, the service still returns retrieved listings and an explicit fallback message in `insight`.

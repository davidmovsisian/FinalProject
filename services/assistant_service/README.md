# Assistant Service

FastAPI microservice responsible for LLM-based insight generation.

## Endpoints

### `GET /health`
Returns service health and LLM availability status.

### `POST /generate-insight`
Generates an insight from a plain-text query and optional similar-listings context.

### `POST /answer-with-listing`
Retrieves similar listings by `listing_id` from RAG service and answers a user question with Gemini using those listings as grounding context.

Request:
```json
{
  "listing_id": "listing-10",
  "question": "Is this listing closer to premium or mid-range in this area?",
  "k": 5
}
```

Response:
```json
{
  "response": "Based on the comparable listings...",
  "similar_listings": [
    {
      "id": "listing-2",
      "distance": 0.1234,
      "listing": {
        "property_type": "apartment",
        "location": "kentron",
        "price": "$125000",
        "overall_condition": "good",
        "living_room": 1,
        "bed_rooms": 2,
        "kitchen": 1,
        "bath_rooms": 1,
        "storage": "yes",
        "features": ["balcony"],
        "conditions": []
      }
    }
  ]
}
```

Request:
```json
{
  "query": "Looking for a renovated apartment in Kentron around $120000",
  "context": "- listing-1: ...\n- listing-2: ..."
}
```

Response:
```json
{
  "insight": "Based on listing-1 and listing-2..."
}
```

## Setup
```bash
cd services/assistant_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run service
```bash
uvicorn main:app --host 0.0.0.0 --port 8001
```

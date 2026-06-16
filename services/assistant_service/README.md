# Assistant Service

FastAPI microservice responsible for LLM-based insight generation.

## Endpoints

### `GET /health`
Returns service health and LLM availability status.

### `POST /generate-insight`
Generates an insight from a plain-text query and optional similar-listings context.

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

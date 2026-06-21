# Guardrails Service (Service 3)

FastAPI microservice that provides content safety guardrails for the AI Property Triage System.
It validates incoming property listing submissions and audits AI-generated property reports
using [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) backed by an OpenAI LLM.

---

## Endpoints

### `GET /health`

Returns service health and guardrails load status.

**Response:**
```json
{
  "status": "ok",
  "rails_loaded": true,
  "llm_model": "gpt-4o-mini"
}
```

---

### `POST /check/input`

Validates that submitted text is a genuine real estate / property listing written in English or Hebrew.
Rejects spam, offensive content, and off-topic submissions.

**Request:**
```json
{ "text": "<text to check>" }
```

**Response (pass):**
```json
{ "passed": true, "reason": "", "safe_text": "<original text>" }
```

**Response (fail):**
```json
{ "passed": false, "reason": "not a property listing", "safe_text": "" }
```

---

### `POST /check/output`

Audits an AI-generated property report to ensure it does not contain false legal claims,
fabricated prices, or invented certifications.

**Request:**
```json
{ "text": "<AI-generated report text>" }
```

**Response (pass):**
```json
{ "passed": true, "reason": "", "safe_text": "<original text>" }
```

**Response (fail):**
```json
{ "passed": false, "reason": "false legal claim detected", "safe_text": "" }
```

---

## Configuration

| Variable               | Required | Default       | Description                                      |
|------------------------|----------|---------------|--------------------------------------------------|
| `OPENAI_API_KEY`       | ✅ Yes   | —             | OpenAI API key used by NeMo Guardrails           |
| `GUARDRAILS_LLM_MODEL` | No       | `gpt-4o-mini` | OpenAI model name used for guardrails evaluation |

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

---

## Local Development

```bash
cd services/guardrails_service
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # fill in OPENAI_API_KEY
uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

The service will be available at `http://localhost:8002`.

---

## Docker

**Build:**
```bash
docker build -t guardrails-service ./services/guardrails_service
```

**Run:**
```bash
docker run -p 8002:8000 \
  -e OPENAI_API_KEY=sk-... \
  -e GUARDRAILS_LLM_MODEL=gpt-4o-mini \
  guardrails-service
```

---

## EC2 Deployment

1. Copy the service directory to the EC2 instance.
2. Build and run the Docker container (see above), mapping port `8002` on the host to `8000` in the container.
3. In the EC2 Security Group, open inbound TCP port `8002` for the sources that need access (e.g., the orchestration layer's IP range or VPC CIDR).

---

## Request / Response Examples

### Check a valid property listing input

```bash
curl -X POST http://localhost:8002/check/input \
  -H "Content-Type: application/json" \
  -d '{"text": "3-bedroom apartment in Tel Aviv, 2nd floor, 85 sqm, asking 2,500,000 NIS. Contact: 050-1234567"}'
```

Expected response:
```json
{"passed": true, "reason": "", "safe_text": "3-bedroom apartment in Tel Aviv..."}
```

### Check spam input

```bash
curl -X POST http://localhost:8002/check/input \
  -H "Content-Type: application/json" \
  -d '{"text": "Click here now to win a free apartment! Limited offer!"}'
```

Expected response:
```json
{"passed": false, "reason": "spam detected — not a genuine property listing", "safe_text": ""}
```

### Check a clean AI-generated output

```bash
curl -X POST http://localhost:8002/check/output \
  -H "Content-Type: application/json" \
  -d '{"text": "Based on comparable sales in the area, this 3BR apartment is estimated to be worth around 2,400,000–2,600,000 NIS."}'
```

Expected response:
```json
{"passed": true, "reason": "", "safe_text": "Based on comparable sales..."}
```

### Check a report with a false legal claim

```bash
curl -X POST http://localhost:8002/check/output \
  -H "Content-Type: application/json" \
  -d '{"text": "This property has a guaranteed freehold title registered at the land registry."}'
```

Expected response:
```json
{"passed": false, "reason": "false legal claim: 'guaranteed freehold title' stated without verified evidence", "safe_text": ""}
```

---

## Guardrails Configuration Guide

### `guardrails/config.yml`

Controls the LLM model, base persona, and which rail flows are activated:

```yaml
models:
  - type: main
    engine: openai
    model: ${GUARDRAILS_LLM_MODEL:-gpt-4o-mini}

rails:
  input:
    flows:
      - check property listing
  output:
    flows:
      - check output safety
```

Change `model` or set `GUARDRAILS_LLM_MODEL` to switch LLM backends.

### `guardrails/colang/input_rails.co`

Defines the Colang 1.0 flows that handle input validation.  
The main flow is `check property listing`, which delegates to the `topic_detection_prompt` subflow.
Edit the inline prompt or add new flows to extend the validation logic.

### `guardrails/colang/output_rails.co`

Defines the Colang 1.0 flows that audit AI-generated outputs.  
The main flow is `check output safety`, which delegates to the `output_auditor_prompt` subflow.
Add new flows to detect additional prohibited content categories.

---

## Prompt Engineering Log Summary

Both the topic detection prompt (for input validation) and the output auditor prompt (for output
auditing) were developed over **5 engineering iterations** each. Each iteration addressed a
specific failure mode observed in testing — including false positives on hedged language, false
negatives on Hebrew-language listings, and over-aggressive flagging of legitimate certifications.
The full iteration log, including each prompt version, observed failure, and final design
decisions, is documented in `guardrails/prompts/topic_detection.txt` and
`guardrails/prompts/output_auditor.txt`.

---

## Testing

### Validate a PASS case (input)

```bash
curl -s -X POST http://localhost:8002/check/input \
  -H "Content-Type: application/json" \
  -d '{"text": "Spacious 4BR villa in Herzliya Pituach with a private pool, 350 sqm, priced at 6,500,000 NIS."}' \
  | python3 -m json.tool
```

Expected: `"passed": true`

### Validate a FAIL case (output)

```bash
curl -s -X POST http://localhost:8002/check/output \
  -H "Content-Type: application/json" \
  -d '{"text": "This property is ISO 9001 certified and guaranteed to sell for $750,000."}' \
  | python3 -m json.tool
```

Expected: `"passed": false`

### Health check

```bash
curl http://localhost:8002/health
```

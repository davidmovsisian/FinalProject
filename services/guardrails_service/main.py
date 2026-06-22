import logging
import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("guardrails_service")

LLM_MODEL = os.getenv("GUARDRAILS_LLM_MODEL", "gpt-4o-mini")


class CheckRequest(BaseModel):
    text: str


class CheckResponse(BaseModel):
    passed: bool
    reason: str = ""
    safe_text: str = ""

async def _call_llm(prompt: str) -> str:
    try:
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        raise


app = FastAPI(
    title="Guardrails Service",
    description="Content safety guardrails for real estate property listings and AI-generated reports.",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY", "")),
        "llm_model": LLM_MODEL,
    }


@app.post("/check/input", response_model=CheckResponse)
async def check_input(request: CheckRequest) -> CheckResponse:
    text = request.text.strip()
    if not text:
        return CheckResponse(passed=False, reason="Empty text submitted.", safe_text="")
    prompt=f"""You are a property listing validator.

TASK: Determine if the submitted text is a genuine property listing in English or Hebrew.

CHECK FOR:
- Spam, off-topic content, or promotional material not about a specific property
- Offensive, hateful, or sexually explicit content
- Non-property real estate content (mortgage rates, investment tips, etc.)
- Proper language (English or Hebrew)

RULES:
- Accept descriptions of specific properties (apartments, houses, commercial space)
- Accept reasonable property-related details (price, location, features)
- Reject general information not about a specific listing
- Prefer PASS for legitimate property listings

TEXT TO VALIDATE:
{text}

Respond ONLY in JSON format with exactly these fields:
{{
    "passed": "true" or "false",
    "reason": "If FAIL, a one-sentence reason. Empty if PASS.",
    "safe_text": "If PASS, return the original text. If FAIL, return an empty string."
}}
"""
    try:
        logger.info("Checking input (length=%d)", len(text))
        response = await _call_llm(prompt)
        print("LLM response:", response)
        verdict = json.loads(response.strip())
        return CheckResponse(
            passed=verdict["passed"] == "true",
            reason=verdict["reason"],
            safe_text=verdict["safe_text"]
        )
    except Exception as exc:
        logger.exception("Error during input check: %s", exc)
        return CheckResponse(passed=False, reason=str(exc), safe_text="")


@app.post("/check/output", response_model=CheckResponse)
async def check_output(request: CheckRequest) -> CheckResponse:
    text = request.text.strip()
    if not text:
        return CheckResponse(passed=False, reason="Empty text submitted.", safe_text="")

    prompt =f"""You are a real estate AI output safety auditor.

TASK: Review the AI-generated property report below and determine whether it
contains any of the following prohibited content:

PROHIBITED CONTENT:
1. FALSE LEGAL CLAIMS — statements that imply legal guarantees or verified legal
   status without evidence (e.g., "guaranteed freehold title", "legally verified
   ownership", "court-certified clear title").
2. FABRICATED PRICE GUARANTEES — invented or unsupported price predictions
   presented as fact (e.g., "guaranteed to sell for $500,000", "will fetch at
   least $X", "price is guaranteed to rise by X%").
3. INVENTED CERTIFICATIONS — certifications or accreditations stated as fact
   without any basis (e.g., "ISO 9001 certified building", "LEED Platinum certified",
   "energy class A certified" when the report has no cited source for this).

RULES:
- Minor hedged opinions are acceptable (e.g., "estimated value around $X", "likely
  freehold based on listing data").
- Only flag content that presents an unverifiable claim as established fact.
- If multiple issues are found, list only the most critical one as the FAIL reason.
- When in doubt, prefer PASS over a false positive.

TEXT TO AUDIT:
{text}

Respond ONLY in JSON format with exactly these fields:
{{
    "passed": "true" or "false",
    "reason": "If FAIL, a one-sentence reason. Empty if PASS.",
    "safe_text": "If PASS, return the original text. If FAIL, return an empty string."
}}"""

    try:
        logger.info("Checking output (length=%d)", len(text))
        response = await _call_llm(prompt)
        print("LLM response:", response)
        verdict = json.loads(response.strip())
        return CheckResponse(
            passed=verdict["passed"] == "true",
            reason=verdict["reason"],
            safe_text=verdict["safe_text"]
        )
    except Exception as exc:
        logger.exception("Error during output check: %s", exc)
        return CheckResponse(passed=False, reason=str(exc), safe_text="")

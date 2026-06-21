import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("guardrails_service")

GUARDRAILS_DIR = Path(__file__).parent / "guardrails"
LLM_MODEL = os.getenv("GUARDRAILS_LLM_MODEL", "gpt-4o-mini")

_rails_input = None
_rails_output = None


class CheckRequest(BaseModel):
    text: str


class CheckResponse(BaseModel):
    passed: bool
    reason: str = ""
    safe_text: str = ""


def _parse_verdict(response: str) -> tuple[bool, str]:
    """Parse a PASS / FAIL: <reason> verdict string from the LLM response."""
    text = response.strip()
    if text.upper().startswith("PASS"):
        return True, ""
    match = re.match(r"^FAIL[:\s]+(.+)$", text, re.IGNORECASE | re.DOTALL)
    if match:
        return False, match.group(1).strip()
    # If the response doesn't match either pattern, treat as fail-safe
    return False, f"Unexpected guardrails response: {text[:200]}"


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _rails_input, _rails_output

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.warning("OPENAI_API_KEY is not set — guardrails LLM calls will fail")

    try:
        from nemoguardrails import LLMRails, RailsConfig

        config = RailsConfig.from_path(str(GUARDRAILS_DIR))
        _rails_input = LLMRails(config)
        _rails_output = LLMRails(config)
        logger.info("NeMo Guardrails loaded from %s (model: %s)", GUARDRAILS_DIR, LLM_MODEL)
    except Exception as exc:
        logger.error("Failed to load NeMo Guardrails: %s", exc)
        _rails_input = None
        _rails_output = None

    yield


app = FastAPI(
    title="Guardrails Service",
    description="Content safety guardrails for real estate property listings and AI-generated reports.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "rails_loaded": _rails_input is not None,
        "llm_model": LLM_MODEL,
    }


@app.post("/check/input", response_model=CheckResponse)
async def check_input(request: CheckRequest) -> CheckResponse:
    """
    Validate that the submitted text is a genuine real estate / property listing
    written in English or Hebrew. Rejects spam, offensive content, and off-topic
    submissions.
    """
    text = request.text.strip()
    if not text:
        return CheckResponse(passed=False, reason="Empty text submitted.", safe_text="")

    if _rails_input is None:
        logger.error("Input rails not loaded; returning fail-safe response")
        return CheckResponse(passed=False, reason="Guardrails service unavailable.", safe_text="")

    try:
        logger.info("Checking input (length=%d)", len(text))
        response = await _rails_input.generate_async(
            messages=[{"role": "user", "content": text}]
        )
        verdict_text = response if isinstance(response, str) else response.get("content", "")
        passed, reason = _parse_verdict(verdict_text)
        logger.info("Input check result: passed=%s reason=%s", passed, reason)
        return CheckResponse(
            passed=passed,
            reason=reason,
            safe_text=text if passed else "",
        )
    except Exception as exc:
        logger.exception("Error during input check: %s", exc)
        return CheckResponse(passed=False, reason=str(exc), safe_text="")


@app.post("/check/output", response_model=CheckResponse)
async def check_output(request: CheckRequest) -> CheckResponse:
    """
    Validate that an AI-generated property report does not contain false legal
    claims, fabricated prices, or invented certifications.
    """
    text = request.text.strip()
    if not text:
        return CheckResponse(passed=False, reason="Empty text submitted.", safe_text="")

    if _rails_output is None:
        logger.error("Output rails not loaded; returning fail-safe response")
        return CheckResponse(passed=False, reason="Guardrails service unavailable.", safe_text="")

    try:
        logger.info("Checking output (length=%d)", len(text))
        response = await _rails_output.generate_async(
            messages=[{"role": "user", "content": text}]
        )
        verdict_text = response if isinstance(response, str) else response.get("content", "")
        passed, reason = _parse_verdict(verdict_text)
        logger.info("Output check result: passed=%s reason=%s", passed, reason)
        return CheckResponse(
            passed=passed,
            reason=reason,
            safe_text=text if passed else "",
        )
    except Exception as exc:
        logger.exception("Error during output check: %s", exc)
        return CheckResponse(passed=False, reason=str(exc), safe_text="")

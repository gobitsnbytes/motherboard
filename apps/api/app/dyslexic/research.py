"""
AI company research for Dyslexic.

Runs on SparkCloud, which has no web-search/grounding tool — the model answers
from what it already knows. That means source URLs it returns are the model's
own claim, not a verified citation, so callers must treat research as
model-generated and unverified rather than fact-checked.

Everything reaches the model through :func:`_call_model`, a single seam tests
replace. The AI is never called in the test suite.

Research is advisory. A failure records why and leaves the company fully
usable — contacts can still be added and emails still logged.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import sentry_sdk

from app.config import get_settings
from app.observability import capture_agent_failure

logger = logging.getLogger(__name__)


RESEARCH_PROMPT = """You are researching a company for a student tech community \
called bits&bytes, which is looking for event sponsors.

Company name: {name}
Website: {website}

You do not have web access. Answer from what you already know about this \
company, then respond with ONLY a JSON object — no markdown fences, no \
commentary before or after — using exactly these keys:

{{
  "summary": "2-3 sentences on what the company actually does",
  "industry": "primary industry",
  "size": "employee count or range if known, else 'Unknown'",
  "headquarters": "city, country if known, else 'Unknown'",
  "products": ["main products or services"],
  "sponsorship_angle": "why this company might sponsor a student tech community — be specific to them, not generic",
  "suggested_contact_roles": ["job titles worth reaching out to for sponsorship"],
  "recent_news": ["notable recent developments, if any"],
  "confidence": "high, medium, or low — how confident you are this is accurate",
  "sources": [{{"title": "short source title", "url": "https://..."}}]
}}

For "sources", only include a URL you are genuinely confident is real and \
correct — an empty list is better than a guessed URL. If you cannot find \
reliable information, say so in the summary and set confidence to "low". Do \
not invent details."""


@dataclass
class ResearchResult:
    """Outcome of one research attempt. Never raises; failures are data."""

    ok: bool
    model: str
    data: dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    error: str | None = None
    sources: list[dict[str, str]] = field(default_factory=list)


def _extract_json(text: str) -> dict[str, Any]:
    """
    Parse a JSON object out of a model response.

    Search grounding and JSON response mode do not combine, so the model returns
    prose-shaped text that usually — but not always — is bare JSON. Strip
    markdown fences, then fall back to the outermost braces.
    """
    cleaned = text.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


# A research call must never hang a background task forever, and a bad network
# blip shouldn't fail the whole company.
MODEL_TIMEOUT_S = 30
# Backstop above the client's own timeout, in case a hang happens below the
# layer that timeout reaches (DNS, a stuck thread). A separate constant, not
# derived from the one above, so a test can shrink it without also changing
# the real request timeout.
MODEL_CALL_TIMEOUT_S = 70


def _call_model(prompt: str, model: str, api_key: str) -> str:
    """
    The single seam through which research reaches SparkCloud.

    Tests monkeypatch this. Synchronous because SparkCloudAIClient's HTTP call
    is, and callers run it in a worker thread.
    """
    from app.services.llm_client import SparkCloudAIClient

    client = SparkCloudAIClient(api_key=api_key, model=model)
    messages = [
        {
            "role": "system",
            "content": "You are a research assistant. Always respond in valid JSON format.",
        },
        {"role": "user", "content": prompt},
    ]
    return client.chat(messages, timeout=MODEL_TIMEOUT_S)


async def research_company(name: str, website: str | None) -> ResearchResult:
    """Research one company. Returns a result object; does not raise."""
    import asyncio

    settings = get_settings()
    model = settings.sparkcloud_model

    if not settings.sparkcloud_api_key:
        return ResearchResult(
            ok=False,
            model=model,
            error="SPARKCLOUD_API_KEY is not configured, so research is unavailable. "
            "You can still add contacts and log outreach.",
        )

    prompt = RESEARCH_PROMPT.format(name=name, website=website or "not provided")

    try:
        # A backstop so a stuck worker thread can never hang the caller — for
        # research that's a background task, but the same seam is reused
        # nowhere it would matter less.
        text = await asyncio.wait_for(
            asyncio.to_thread(_call_model, prompt, model, settings.sparkcloud_api_key),
            timeout=MODEL_CALL_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("Research model call timed out")
        capture_agent_failure(
            agent="dyslexic_research", operation="model_call", reason="timeout"
        )
        return ResearchResult(
            ok=False, model=model, error="Research timed out. Try again."
        )
    except Exception as exc:
        logger.warning("Research model call failed: %s", type(exc).__name__)
        capture_agent_failure(
            agent="dyslexic_research", operation="model_call", reason=type(exc).__name__
        )
        return ResearchResult(
            ok=False, model=model, error="Research call failed. Try again."
        )

    if not text.strip():
        capture_agent_failure(
            agent="dyslexic_research", operation="model_call", reason="empty_response"
        )
        return ResearchResult(
            ok=False, model=model, error="The model returned an empty response."
        )

    try:
        data = _extract_json(text)
    except (json.JSONDecodeError, ValueError) as exc:
        capture_agent_failure(
            agent="dyslexic_research", operation="parse", reason="invalid_json"
        )
        # Keep the raw text — a bad response should be debuggable, not lost.
        return ResearchResult(
            ok=False,
            model=model,
            raw=text,
            error=f"Could not parse the model's response as JSON: {exc}",
        )

    # SparkCloud has no search/grounding tool, so any source URLs came from the
    # model's own claim in-band, not a verified citation — never fabricate a
    # shape for this field if the model omitted or mangled it.
    sources = data.get("sources")
    sources = sources if isinstance(sources, list) else []
    data["sources"] = sources

    return ResearchResult(ok=True, model=model, data=data, raw=text, sources=sources)


def _session_factory():
    """
    Where the background task gets its database session.

    A module-level indirection, like :func:`_call_model`, so tests can lend the
    task their own session — by the time this runs the request's session is long
    gone.
    """
    from app.database import get_sessionmaker

    return get_sessionmaker()


async def run_research_task(company_id: uuid.UUID) -> None:
    """
    Background entry point: research a company and store the outcome.

    Wrapped end to end — an unhandled exception here must never leave a company
    stuck showing "researching" forever.
    """
    from app.db.models import DyslexicCompany
    from app.dyslexic import service
    from app.events import event_bus

    session_factory = _session_factory()

    try:
        async with session_factory() as session:
            company = await session.get(DyslexicCompany, company_id)
            if company is None:
                return
            company.research_status = "running"
            await session.commit()
            name, website = company.name, company.website

        with sentry_sdk.start_transaction(
            op="ai.pipeline", name="Dyslexic company research"
        ):
            result = await research_company(name, website)

        async with session_factory() as session:
            company = await session.get(DyslexicCompany, company_id)
            if company is None:
                return

            if result.ok:
                company.research_status = "complete"
                company.research_json = result.data
                company.research_raw = result.raw
                company.research_error = None
                summary = f"AI research completed for {company.name}"
                kind = "research.generated"
            else:
                company.research_status = "failed"
                company.research_raw = result.raw or None
                company.research_error = result.error
                summary = f"AI research failed for {company.name}"
                kind = "research.failed"

            company.research_model = result.model
            company.research_generated_at = datetime.now(timezone.utc)

            await service.record_event(
                session,
                company_id=company.id,
                actor_id=None,
                kind=kind,
                summary=summary,
                metadata={"model": result.model, "error": result.error},
            )
            await session.commit()

        try:
            await event_bus.publish(
                "dyslexic.research.completed",
                {"company_id": str(company_id), "ok": result.ok},
            )
        except Exception:
            logger.warning("Could not publish research completion", exc_info=True)

    except Exception:
        logger.exception("Research task crashed for company %s", company_id)
        # Never leave the row in `running` — the UI would show a spinner forever.
        try:
            async with session_factory() as session:
                company = await session.get(DyslexicCompany, company_id)
                if company and company.research_status == "running":
                    company.research_status = "failed"
                    company.research_error = "Research task failed unexpectedly."
                    await session.commit()
        except Exception:
            logger.exception("Could not mark research failed for %s", company_id)

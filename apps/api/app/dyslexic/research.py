"""
AI company research for Dyslexic.

Grounded in Google Search rather than the model's memory, because the sponsors
volunteers add are often small companies the model would otherwise invent
details about. Source URLs come from the response's grounding metadata, not from
the model's prose, so a citation cannot be fabricated.

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

from app.config import get_settings

logger = logging.getLogger(__name__)


RESEARCH_PROMPT = """You are researching a company for a student tech community \
called bits&bytes, which is looking for event sponsors.

Company name: {name}
Website: {website}

Search for current information about this company, then respond with ONLY a \
JSON object — no markdown fences, no commentary before or after — using exactly \
these keys:

{{
  "summary": "2-3 sentences on what the company actually does",
  "industry": "primary industry",
  "size": "employee count or range if known, else 'Unknown'",
  "headquarters": "city, country if known, else 'Unknown'",
  "products": ["main products or services"],
  "sponsorship_angle": "why this company might sponsor a student tech community — be specific to them, not generic",
  "suggested_contact_roles": ["job titles worth reaching out to for sponsorship"],
  "recent_news": ["notable recent developments, if any"],
  "confidence": "high, medium, or low — how confident you are this is accurate"
}}

If you cannot find reliable information, say so in the summary and set \
confidence to "low". Do not invent details."""


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


def _extract_sources(response: Any) -> list[dict[str, str]]:
    """
    Pull citations from grounding metadata.

    Reading these from the response structure rather than the model's text is
    what makes them trustworthy — the model cannot write a URL it did not visit
    into this field.
    """
    sources: list[dict[str, str]] = []
    try:
        for candidate in getattr(response, "candidates", None) or []:
            metadata = getattr(candidate, "grounding_metadata", None)
            for chunk in getattr(metadata, "grounding_chunks", None) or []:
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    entry = {
                        "title": getattr(web, "title", "") or web.uri,
                        "url": web.uri,
                    }
                    if entry not in sources:
                        sources.append(entry)
    except Exception:  # pragma: no cover - metadata shape varies by model
        logger.debug("Could not read grounding metadata", exc_info=True)
    return sources


def _call_model(prompt: str, model: str, api_key: str) -> tuple[str, list[dict[str, str]]]:
    """
    The single seam through which research reaches Gemini.

    Tests monkeypatch this. Synchronous because the google-genai client is, and
    callers run it in a worker thread.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    return (response.text or ""), _extract_sources(response)


async def research_company(name: str, website: str | None) -> ResearchResult:
    """Research one company. Returns a result object; does not raise."""
    import asyncio

    settings = get_settings()
    model = settings.dyslexic_gemini_model

    if not settings.gemini_api_key:
        return ResearchResult(
            ok=False,
            model=model,
            error="GEMINI_API_KEY is not configured, so research is unavailable. "
            "You can still add contacts and log outreach.",
        )

    prompt = RESEARCH_PROMPT.format(name=name, website=website or "not provided")

    try:
        text, sources = await asyncio.to_thread(
            _call_model, prompt, model, settings.gemini_api_key
        )
    except Exception as exc:
        logger.warning("Research call failed for %s: %s", name, exc)
        return ResearchResult(ok=False, model=model, error=f"Research call failed: {exc}")

    if not text.strip():
        return ResearchResult(
            ok=False, model=model, error="The model returned an empty response."
        )

    try:
        data = _extract_json(text)
    except (json.JSONDecodeError, ValueError) as exc:
        # Keep the raw text — a bad response should be debuggable, not lost.
        return ResearchResult(
            ok=False,
            model=model,
            raw=text,
            error=f"Could not parse the model's response as JSON: {exc}",
        )

    if sources:
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

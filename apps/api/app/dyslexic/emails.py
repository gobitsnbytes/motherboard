"""
Sponsor email drafting for Dyslexic.

Ungrounded — unlike research, this is a writing task, not a fact-finding one.
The company research already gathered the facts; this turns them into a note a
volunteer can send.

Nothing here sends email. The draft is editable in the UI and the volunteer
copies it into Gmail themselves, which is deliberate: outreach from a student
community should come from a person's own mailbox.

Brand rules from docs/design.md are enforced in the prompt — "bits&bytes" is
always lowercase with the ampersand, and the legal entity name is reserved for
legal contexts.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)


BRAND_RULES = """About the sender:
- The community is called "bits&bytes" — always lowercase, always with the \
ampersand. Never write "Bits & Bytes", "B&B", or "bits and bytes".
- It is a student-run tech community across Indian cities, running events, \
hackathons and workshops.
- Do not mention a legal entity name.
- The volunteer writing this is a student, not a salesperson. Write like one: \
direct, specific, and without corporate filler."""


INITIAL_PROMPT = """Write a sponsorship outreach email to a contact at a company.

{brand}

Company: {company_name}
What we know about them:
{research}

Contact: {contact_name}
Their role: {contact_role}

{extra}

Requirements:
- Reference something specific and true about this company. If the research \
above is thin, keep it general rather than inventing details.
- Say clearly what bits&bytes is asking for and what the company gets.
- Keep it under 180 words. Nobody reads a long cold email.
- {tone_line}
- No placeholder text like [Your Name] — end with a plain sign-off.

Respond with ONLY a JSON object, no markdown fences:
{{"subject": "...", "body": "..."}}"""


FOLLOW_UP_PROMPT = """Write a short follow-up to a sponsorship email that got no reply.

{brand}

Company: {company_name}
Contact: {contact_name}
Their role: {contact_role}

The original email, sent {days_ago} days ago:
Subject: {previous_subject}
{previous_body}

{extra}

Requirements:
- Under 90 words. A follow-up should be shorter than the original.
- Polite, not passive-aggressive. Assume they were busy, not uninterested.
- Add one new reason to care rather than only repeating the first email.
- {tone_line}
- No placeholder text like [Your Name] — end with a plain sign-off.

Respond with ONLY a JSON object, no markdown fences:
{{"subject": "...", "body": "..."}}"""


@dataclass
class DraftResult:
    """Outcome of one drafting attempt. Never raises; failures are data."""

    ok: bool
    model: str
    subject: str = ""
    body: str = ""
    raw: str = ""
    error: str | None = None


def _call_model(prompt: str, model: str, api_key: str) -> str:
    """
    The single seam through which drafting reaches Gemini.

    Tests monkeypatch this. Unlike research this asks for JSON directly, since
    there is no search tool to conflict with response formatting.
    """
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )
    return response.text or ""


def _summarise_research(research_json: dict[str, Any]) -> str:
    """Flatten the research blob into prompt-friendly lines."""
    if not research_json:
        return "No research available — keep the email general."

    interesting = [
        ("Summary", research_json.get("summary")),
        ("Industry", research_json.get("industry")),
        ("Size", research_json.get("size")),
        ("Headquarters", research_json.get("headquarters")),
        ("Why they might sponsor", research_json.get("sponsorship_angle")),
    ]
    lines = [f"- {label}: {value}" for label, value in interesting if value]

    for label, key in [("Products", "products"), ("Recent news", "recent_news")]:
        values = research_json.get(key)
        if isinstance(values, list) and values:
            lines.append(f"- {label}: {', '.join(str(v) for v in values[:3])}")

    return "\n".join(lines) or "No research available — keep the email general."


async def generate_email(
    *,
    company_name: str,
    research_json: dict[str, Any] | None,
    contact_name: str,
    contact_role: str | None,
    kind: str = "initial",
    tone: str | None = None,
    extra_context: str | None = None,
    previous_subject: str | None = None,
    previous_body: str | None = None,
    days_ago: int = 3,
) -> DraftResult:
    """Draft one email. Returns a result object; does not raise."""
    import asyncio

    settings = get_settings()
    model = settings.dyslexic_gemini_model

    if not settings.gemini_api_key:
        return DraftResult(
            ok=False,
            model=model,
            error="GEMINI_API_KEY is not configured, so drafting is unavailable. "
            "You can write the email yourself and still log it as sent.",
        )

    tone_line = (
        f"Tone: {tone}." if tone else "Tone: warm and straightforward."
    )
    extra = f"The volunteer added: {extra_context}" if extra_context else ""

    if kind == "follow_up":
        prompt = FOLLOW_UP_PROMPT.format(
            brand=BRAND_RULES,
            company_name=company_name,
            contact_name=contact_name,
            contact_role=contact_role or "unknown",
            days_ago=days_ago,
            previous_subject=previous_subject or "(not recorded)",
            previous_body=previous_body or "(not recorded)",
            extra=extra,
            tone_line=tone_line,
        )
    else:
        prompt = INITIAL_PROMPT.format(
            brand=BRAND_RULES,
            company_name=company_name,
            research=_summarise_research(research_json or {}),
            contact_name=contact_name,
            contact_role=contact_role or "unknown",
            extra=extra,
            tone_line=tone_line,
        )

    try:
        text = await asyncio.to_thread(
            _call_model, prompt, model, settings.gemini_api_key
        )
    except Exception as exc:
        logger.warning("Draft generation failed for %s: %s", company_name, exc)
        return DraftResult(ok=False, model=model, error=f"Drafting failed: {exc}")

    if not text.strip():
        return DraftResult(
            ok=False, model=model, error="The model returned an empty response."
        )

    try:
        from .research import _extract_json

        data = _extract_json(text)
    except (json.JSONDecodeError, ValueError) as exc:
        return DraftResult(
            ok=False,
            model=model,
            raw=text,
            error=f"Could not parse the model's response as JSON: {exc}",
        )

    subject = str(data.get("subject") or "").strip()
    body = str(data.get("body") or "").strip()

    if not subject or not body:
        return DraftResult(
            ok=False,
            model=model,
            raw=text,
            error="The model's response was missing a subject or body.",
        )

    return DraftResult(ok=True, model=model, subject=subject, body=body, raw=text)

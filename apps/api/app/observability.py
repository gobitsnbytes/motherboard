"""Sentry setup, event scrubbing, and reporting helpers for the API."""

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger

logger = logging.getLogger(__name__)

# Request lifecycle logs duplicate what the FastAPI integration already captures.
REQUEST_LOGGER = "app.request"

_FILTERED = "[Filtered]"
_SENSITIVE_KEY = re.compile(
    r"auth(?!or)|cookie|token|secret|passw|pwd|dsn|api[-_]?key|credential|private[-_]?key|webhook|(?:^|[-_])otp(?:$|[-_])",
    re.IGNORECASE,
)
_SECRET_PATTERNS = (
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer " + _FILTERED),
    (re.compile(r"(?i)\bbot\s+[A-Za-z0-9._-]{20,}"), "Bot " + _FILTERED),
    # Credentials in any URL: DSNs, database/redis URLs, webhook basic auth.
    (
        re.compile(r"([a-z][a-z0-9+.-]*://)[^/\s:@]+(?::[^/\s@]*)?@"),
        r"\1" + _FILTERED + "@",
    ),
    (
        re.compile(r"(?i)(/sign/|/public/|/webhooks/[^/\s]+/)(?!\{)[^/\s?#]+"),
        r"\1" + _FILTERED,
    ),
    (
        re.compile(
            r"(?i)([?&][^=&\s]*(?:token|secret|key|sig|code|pass)[^=&\s]*=)[^&\s#]+"
        ),
        r"\1" + _FILTERED,
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}|\bsc-ai-[A-Za-z0-9_-]{8,}"), _FILTERED),
    # Needs a letter TLD so "pkg@1.2.3" version strings survive.
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[A-Za-z]{2,}\b"), "[email]"),
)
_SAFE_HEADERS = {
    "user-agent",
    "content-type",
    "content-length",
    "accept",
    "x-request-id",
    "host",
}
_NO_TRACE_PATHS = ("/health", "/api/health")
_LOG_EVENTS = {"api.request.completed", "api.request.failed", "agent.run.failed"}
_LOG_ATTRIBUTES = {
    "method",
    "route",
    "status_code",
    "duration_ms",
    "request_id",
    "agent",
    "operation",
    "reason",
}


def scrub_text(value: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def _scrub(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return _FILTERED
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {
            k: _FILTERED
            if isinstance(k, str) and _SENSITIVE_KEY.search(k)
            else _scrub(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(v, depth + 1) for v in value]
    return value


def _strip_query(url: str) -> str:
    parts = urlsplit(url)
    return scrub_text(urlunsplit((parts.scheme, parts.netloc, parts.path, "", "")))


def _scrub_request(event: dict[str, Any]) -> None:
    request = event.get("request")
    if not isinstance(request, dict):
        return
    for key in ("cookies", "data", "query_string", "env"):
        request.pop(key, None)
    url = request.get("url")
    if isinstance(url, str):
        # Prefer the route template ("/api/signatures/sign/{token}") over the raw path.
        info = event.get("transaction_info") or {}
        transaction = event.get("transaction")
        if (
            info.get("source") == "route"
            and isinstance(transaction, str)
            and transaction.startswith("/")
        ):
            parts = urlsplit(url)
            url = urlunsplit((parts.scheme, parts.netloc, transaction, "", ""))
        request["url"] = _strip_query(url)
    headers = request.get("headers")
    if isinstance(headers, dict):
        request["headers"] = {
            k: v for k, v in headers.items() if k.lower() in _SAFE_HEADERS
        }


def _scrub_event(event: dict[str, Any]) -> dict[str, Any]:
    _scrub_request(event)
    if (event.get("tags") or {}).get("telemetry_kind") == "ai_agent":
        # Prior breadcrumbs or scope extras can contain prompts and document text.
        event.pop("breadcrumbs", None)
        event.pop("extra", None)
        event.pop("user", None)
        contexts = event.get("contexts") or {}
        event["contexts"] = {
            key: value for key, value in contexts.items() if key in {"trace", "runtime"}
        }
    for key in ("extra", "contexts", "tags"):
        if key in event:
            event[key] = _scrub(event[key])
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        # Formatted message and raw params can both carry secrets.
        logentry.pop("params", None)
        for field in ("message", "formatted"):
            if isinstance(logentry.get(field), str):
                logentry[field] = scrub_text(logentry[field])
    for exc in (event.get("exception") or {}).get("values") or []:
        if isinstance(exc.get("value"), str):
            exc["value"] = scrub_text(exc["value"])
    crumbs = event.get("breadcrumbs")
    values = crumbs.get("values") if isinstance(crumbs, dict) else crumbs
    for crumb in values or []:
        if isinstance(crumb.get("message"), str):
            crumb["message"] = scrub_text(crumb["message"])
        data = crumb.get("data")
        if isinstance(data, dict):
            if isinstance(data.get("url"), str):
                data["url"] = _strip_query(data["url"])
            data.pop("http.query", None)
            data.pop("http.fragment", None)
            crumb["data"] = _scrub(data)
    return event


def before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    exc_info = hint.get("exc_info")
    if exc_info and _is_expected(exc_info[1]):
        return None
    return _scrub_event(event)


def before_send_transaction(
    event: dict[str, Any], hint: dict[str, Any]
) -> dict[str, Any]:
    return _scrub_event(event)


def before_send_log(log: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Only explicit, structured operational logs may leave the process."""
    if log.get("body") not in _LOG_EVENTS:
        return None
    log["attributes"] = {
        key: value
        for key, value in (log.get("attributes") or {}).items()
        if key in _LOG_ATTRIBUTES and isinstance(value, (str, int, float))
    }
    return log


def emit_runtime_log(event: str, **attributes: str | int | float) -> None:
    if event in _LOG_EVENTS and sentry_sdk.get_client().is_active():
        sentry_sdk.logger.info(event, attributes=attributes)


def _is_expected(exc: BaseException | None) -> bool:
    """Client errors and validation failures are normal control flow, not issues."""
    from fastapi.exceptions import RequestValidationError
    from pydantic import ValidationError
    from starlette.exceptions import HTTPException

    if isinstance(exc, HTTPException):
        return exc.status_code < 500
    return isinstance(exc, (RequestValidationError, ValidationError))


def git_sha(start: Path | None = None) -> str | None:
    """Read the checkout's HEAD commit from .git without shelling out to git."""
    for directory in [
        (start or Path(__file__)).resolve(),
        *(start or Path(__file__)).resolve().parents,
    ]:
        git_dir = directory / ".git"
        if not git_dir.is_dir():
            continue
        try:
            head = (git_dir / "HEAD").read_text().strip()
            if not head.startswith("ref: "):
                return head[:40] or None
            ref = head[5:]
            ref_file = git_dir / ref
            if ref_file.is_file():
                return ref_file.read_text().strip()[:40] or None
            for line in (git_dir / "packed-refs").read_text().splitlines():
                if line.endswith(" " + ref):
                    return line.split(" ", 1)[0]
        except OSError:
            return None
        return None
    return None


def release_name(settings) -> str:
    if settings.sentry_release:
        return settings.sentry_release
    sha = git_sha()
    return f"bnb-api@{settings.app_version}" + (f"+{sha[:12]}" if sha else "")


def traces_rate(settings) -> float:
    if settings.sentry_traces_sample_rate is not None:
        return min(max(settings.sentry_traces_sample_rate, 0.0), 1.0)
    return 0.02 if settings.sentry_environment == "production" else 0.0


def _traces_sampler(rate: float):
    def sampler(context: dict[str, Any]) -> float:
        path = (context.get("asgi_scope") or {}).get("path", "")
        if path in _NO_TRACE_PATHS or path.startswith("/api/health"):
            return 0.0
        parent = context.get("parent_sampled")
        return float(parent) if parent is not None else rate

    return sampler


def init_sentry(settings) -> bool:
    """Initialize Sentry once per process. Returns True when reporting is enabled."""
    dsn = (settings.sentry_dsn or "").strip()
    if not dsn:
        return False
    client = sentry_sdk.get_client()
    if client.is_active() and client.options.get("dsn") == dsn:
        return True  # repeated create_app() calls reuse the existing client
    ignore_logger(REQUEST_LOGGER)
    sentry_sdk.init(
        dsn=dsn,
        environment=settings.sentry_environment,
        release=release_name(settings),
        send_default_pii=False,
        max_request_body_size="never",
        include_local_variables=False,
        traces_sampler=_traces_sampler(traces_rate(settings)),
        before_send=before_send,
        before_send_transaction=before_send_transaction,
        before_send_log=before_send_log,
        enable_logs=True,
        integrations=[
            LoggingIntegration(
                level=logging.INFO, event_level=logging.ERROR, sentry_logs_level=None
            )
        ],
        shutdown_timeout=2,
    )
    sentry_sdk.set_tag("service", "bnb-api")
    return True


def capture_background_exception(
    exc: BaseException, *, subsystem: str, operation: str
) -> None:
    """Report an unexpected failure that the caller handles and does not re-raise."""
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("subsystem", subsystem)
        scope.set_tag("operation", operation)
        sentry_sdk.capture_exception(exc)


def capture_agent_failure(*, agent: str, operation: str, reason: str) -> None:
    """Report a handled AI failure without forwarding prompts or provider output."""
    with sentry_sdk.new_scope() as scope:
        scope.clear_breadcrumbs()
        scope.set_user(None)
        scope.set_tag("subsystem", agent)
        scope.set_tag("operation", operation)
        scope.set_tag("failure_reason", reason)
        scope.set_tag("telemetry_kind", "ai_agent")
        sentry_sdk.capture_message(f"{agent}.{operation} failed", level="error")
    emit_runtime_log(
        "agent.run.failed", agent=agent, operation=operation, reason=reason
    )

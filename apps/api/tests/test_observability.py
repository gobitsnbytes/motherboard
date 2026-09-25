"""Sentry configuration, scrubbing, filtering, and capture paths."""

import asyncio
import io
import json
import urllib.error
from types import SimpleNamespace

import pytest
import sentry_sdk
import redis.exceptions
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app import observability
from app.events.bus import EventBus
from app.services.llm_client import SparkCloudAIClient

FAKE_DSN = "https://public@example.invalid/1"


def test_llm_provider_error_does_not_leak_response_body(
    monkeypatch, caplog, sentry_events
):
    private_body = "private contract terms must stay private"

    def reject_request(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://cloud.example.invalid/chat/completions",
            429,
            "rate limited",
            {},
            io.BytesIO(private_body.encode()),
        )

    monkeypatch.setattr(
        "app.services.llm_client.urllib.request.urlopen", reject_request
    )
    client = SparkCloudAIClient(
        api_key="test", base_url="https://cloud.example.invalid"
    )

    with pytest.raises(RuntimeError, match="status 429") as failure:
        client.chat([{"role": "user", "content": private_body}])

    assert private_body not in str(failure.value)
    assert private_body not in caplog.text
    sentry_sdk.capture_exception(failure.value)
    assert private_body not in json.dumps(sentry_events[-1])


def test_llm_parse_warning_does_not_leak_output(monkeypatch, caplog):
    private_output = "private contract terms are not JSON"
    client = SparkCloudAIClient(api_key="test")
    monkeypatch.setattr(
        client, "_chat_completion", lambda *args, **kwargs: private_output
    )

    result = client.analyze_clause_risk("private-ref", "heading", "clause")

    assert result["has_risk"] is False
    assert private_output not in caplog.text


def test_llm_reports_only_token_counts_to_sentry(monkeypatch):
    seen = []
    response = {
        "choices": [{"message": {"content": "private generated answer"}}],
        "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
    }
    monkeypatch.setattr(
        "app.services.llm_client.urllib.request.urlopen",
        lambda *args, **kwargs: io.BytesIO(json.dumps(response).encode()),
    )
    monkeypatch.setattr(
        "app.services.llm_client.record_token_usage",
        lambda span, **counts: seen.append(counts),
    )

    client = SparkCloudAIClient(api_key="test")
    assert (
        client.chat([{"role": "user", "content": "private request"}])
        == "private generated answer"
    )
    assert seen == [{"input_tokens": 12, "output_tokens": 5, "total_tokens": 17}]


def test_handled_agent_failure_has_safe_operation_context(sentry_events):
    sentry_sdk.add_breadcrumb(message="private contract text")
    observability.capture_agent_failure(
        agent="legal_agent", operation="policy_synthesis", reason="TimeoutError"
    )

    event = sentry_events[-1]
    assert event["tags"]["subsystem"] == "legal_agent"
    assert event["tags"]["operation"] == "policy_synthesis"
    assert event["tags"]["failure_reason"] == "TimeoutError"
    assert "policy_synthesis failed" in json.dumps(event)
    assert "private contract text" not in json.dumps(event)


class RecordingTransport(Transport):
    def __init__(self):
        super().__init__()
        self.events = []
        self.logs = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)
            if item.type == "log":
                self.logs.extend(item.payload.json["items"])


def _settings(**overrides):
    base = dict(
        sentry_dsn=FAKE_DSN,
        sentry_environment="test",
        sentry_traces_sample_rate=None,
        sentry_release=None,
        app_version="1.2.3",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture
def sentry_events():
    assert observability.init_sentry(_settings())
    transport = RecordingTransport()
    sentry_sdk.get_client().transport = transport
    yield transport.events
    sentry_sdk.init(dsn=None)


def test_structured_logs_keep_only_allowlisted_data():
    assert observability.init_sentry(_settings())
    transport = RecordingTransport()
    sentry_sdk.get_client().transport = transport
    try:
        sentry_sdk.logger.info("private contract text")
        sentry_sdk.logger.info(
            "api.request.completed",
            attributes={
                "route": "/api/users",
                "status_code": 200,
                "prompt": "private contract text",
            },
        )
        sentry_sdk.flush()
        assert len(transport.logs) == 1
        assert transport.logs[0]["body"] == "api.request.completed"
        assert "private contract text" not in json.dumps(transport.logs)
        assert "prompt" not in json.dumps(transport.logs)
    finally:
        sentry_sdk.init(dsn=None)


def test_request_log_uses_route_template(monkeypatch):
    from app.main import create_app

    emitted = []
    monkeypatch.setattr(
        "app.main.emit_runtime_log",
        lambda event, **attrs: emitted.append((event, attrs)),
    )
    app = create_app()

    @app.get("/api/log-test/{private_value}")
    async def log_test(private_value: str):
        return {"ok": True}

    response = TestClient(app).get("/api/log-test/private-customer-name")
    assert response.status_code == 200
    assert emitted[-1][0] == "api.request.completed"
    assert emitted[-1][1]["route"] == "/api/log-test/{private_value}"
    assert "private-customer-name" not in str(emitted)


def test_blank_dsn_disables_sentry():
    assert observability.init_sentry(_settings(sentry_dsn="  ")) is False
    assert observability.init_sentry(_settings(sentry_dsn=None)) is False


def test_release_and_environment(sentry_events):
    options = sentry_sdk.get_client().options
    assert options["environment"] == "test"
    assert options["release"].startswith("bnb-api@1.2.3")
    assert options["send_default_pii"] is False
    assert options["include_local_variables"] is False
    assert (
        observability.release_name(_settings(sentry_release="bnb-api@custom"))
        == "bnb-api@custom"
    )


def test_git_sha_reads_packed_refs(tmp_path):
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("ref: refs/heads/prod\n")
    (git / "packed-refs").write_text("abc123 refs/heads/prod\n")
    assert observability.git_sha(tmp_path) == "abc123"


def test_trace_rate_defaults_are_conservative():
    assert observability.traces_rate(_settings(sentry_environment="production")) == 0.02
    assert observability.traces_rate(_settings(sentry_environment="development")) == 0.0
    assert observability.traces_rate(_settings(sentry_traces_sample_rate=5)) == 1.0
    sampler = observability._traces_sampler(0.5)
    assert sampler({"asgi_scope": {"path": "/api/health/ready"}}) == 0.0
    assert sampler({"asgi_scope": {"path": "/api/users"}}) == 0.5
    assert sampler({"parent_sampled": True, "asgi_scope": {"path": "/x"}}) == 1.0


def test_repeated_init_reuses_client(sentry_events):
    client = sentry_sdk.get_client()
    assert observability.init_sentry(_settings())
    assert sentry_sdk.get_client() is client


def test_scrubs_request_url_headers_query_and_context():
    event = {
        "transaction": "/api/signatures/sign/{token}",
        "transaction_info": {"source": "route"},
        "request": {
            "url": "https://api.example.org/api/signatures/sign/s3cr3t-token?otp=123",
            "query_string": "otp=123",
            "cookies": {"session": "abc"},
            "data": {"password": "x"},
            "headers": {
                "Authorization": "Bearer abc.def",
                "Cookie": "session=abc",
                "User-Agent": "pytest",
                "X-Request-ID": "req-1",
            },
        },
        "extra": {"api_key": "k", "note": "postgresql://u:p@db/x Bearer zzz"},
        "logentry": {"message": "mail to a@b.org failed", "params": ["a@b.org"]},
        "breadcrumbs": {
            "values": [
                {
                    "data": {
                        "url": "https://discord.com/api?token=abc",
                        "http.query": "token=abc",
                    }
                }
            ]
        },
    }
    out = observability.before_send(event, {})
    request = out["request"]
    assert request["url"] == "https://api.example.org/api/signatures/sign/{token}"
    assert set(request["headers"]) == {"User-Agent", "X-Request-ID"}
    assert not {"query_string", "cookies", "data"} & set(request)
    assert out["extra"]["api_key"] == "[Filtered]"
    assert "u:p" not in out["extra"]["note"] and "zzz" not in out["extra"]["note"]
    assert out["logentry"] == {"message": "mail to [email] failed"}
    crumb = out["breadcrumbs"]["values"][0]["data"]
    assert crumb == {"url": "https://discord.com/api"}


def test_scrubs_raw_secret_paths_without_route_template():
    text = observability.scrub_text(
        "GET /api/onboarding/public/abc123/submit "
        "https://key@o1.ingest.sentry.io/2 ?token=zz&x=1"
    )
    assert "abc123" not in text and "key@" not in text and "zz" not in text


def test_expected_errors_are_dropped():
    def hint(exc):
        return {"exc_info": (type(exc), exc, None)}

    assert observability.before_send({}, hint(HTTPException(status_code=404))) is None
    assert observability.before_send({}, hint(HTTPException(status_code=503))) == {}
    assert observability.before_send({}, hint(RuntimeError("boom"))) == {}


def test_unhandled_route_error_is_captured_once_with_request_id(sentry_events):
    from app.main import create_app

    app = create_app()

    @app.get("/api/signatures/sign/{token}/boom-test")
    async def boom(token: str):
        raise RuntimeError("controlled failure")

    @app.get("/api/expected-404-test")
    async def missing():
        raise HTTPException(status_code=404)

    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/api/expected-404-test").status_code == 404
    response = client.get(
        "/api/signatures/sign/secret-tok/boom-test?otp=9",
        headers={"X-Request-ID": "req-abc", "Authorization": "Bearer nope"},
    )
    assert response.status_code == 500
    sentry_sdk.flush()

    assert len(sentry_events) == 1
    event = sentry_events[0]
    assert event["tags"]["request_id"] == "req-abc"
    assert "secret-tok" not in str(event["request"])
    assert "Authorization" not in event["request"].get("headers", {})
    assert event["exception"]["values"][-1]["value"] == "controlled failure"


async def test_event_bus_subscriber_failure_is_captured(sentry_events):
    bus = EventBus()

    async def failing(payload):
        raise ValueError("subscriber broke")

    bus.subscribe("demo.event", failing)
    await bus.publish("demo.event", {"body": "private"})
    await asyncio.sleep(0.05)
    sentry_sdk.flush()

    assert len(sentry_events) == 1
    event = sentry_events[0]
    assert event["tags"]["subsystem"] == "event_bus"
    assert event["tags"]["operation"] == "demo.event"
    # Frames carry source lines of this test; the payload itself must not appear.
    assert "private" not in str({k: v for k, v in event.items() if k != "exception"})


async def test_event_bus_reconnects_after_pubsub_write_timeout(monkeypatch, caplog):
    class FailingPubSub:
        closed = False
        pinged = False

        async def subscribe(self, channel):
            assert channel == "motherboard_events"

        async def listen(self):
            raise redis.exceptions.TimeoutError(
                "Timeout writing to socket: private payload"
            )
            yield None

        async def ping(self):
            self.pinged = True
            raise redis.exceptions.TimeoutError(
                "Timeout writing to socket: private payload"
            )

        async def aclose(self):
            self.closed = True

    pubsub = FailingPubSub()
    bus = EventBus()
    bus.redis = SimpleNamespace(pubsub=lambda: pubsub)
    captured = []
    logs = []

    async def stop_after_retry(seconds):
        assert seconds == 2
        bus.redis = None

    monkeypatch.setattr("app.events.bus.asyncio.sleep", stop_after_retry)
    monkeypatch.setattr(
        "app.events.bus.capture_background_exception",
        lambda exc, **context: captured.append(context),
    )
    monkeypatch.setattr(
        "app.events.bus.emit_runtime_log", lambda event: logs.append(event)
    )

    await bus._redis_listener()

    assert pubsub.pinged and pubsub.closed
    assert bus._pubsub is None
    assert captured == [{"subsystem": "event_bus", "operation": "listen"}]
    assert logs == ["api.event_bus.connected", "api.event_bus.reconnecting"]
    assert "private payload" not in caplog.text


def test_scrubber_keeps_version_strings_and_ids():
    assert (
        observability.scrub_text("sentry-sdk@2.70.0 failed")
        == "sentry-sdk@2.70.0 failed"
    )
    kept = observability._scrub({"session_id": "s1", "signature_request_id": "r1"})
    assert kept == {"session_id": "s1", "signature_request_id": "r1"}
    assert observability._scrub({"otp": "1", "access_token": "t"}) == {
        "otp": "[Filtered]",
        "access_token": "[Filtered]",
    }

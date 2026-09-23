"""Sentry configuration, scrubbing, filtering, and capture paths."""

import asyncio
from types import SimpleNamespace

import pytest
import sentry_sdk
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sentry_sdk.transport import Transport

from app import observability
from app.events.bus import EventBus

FAKE_DSN = "https://public@example.invalid/1"


class RecordingTransport(Transport):
    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


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

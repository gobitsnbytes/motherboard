"""
The SSE hub.

Correctness never depends on the stream — the duplicate guard is in the
database — so these tests are about the stream not breaking anything else:
queues must not leak on disconnect, and a client that stops reading must not
grow one without limit.
"""

import asyncio
import json
import time

import pytest

from app.events.sse import (
    DEDUPE_MAX_ENTRIES,
    DEDUPE_SECONDS,
    HEARTBEAT_SECONDS,
    MAX_QUEUED_EVENTS,
    SseHub,
)


async def read_frames(hub: SseHub, count: int, timeout: float = 2.0) -> list[str]:
    """Drain `count` frames from a fresh stream, then close it."""
    frames: list[str] = []
    stream = hub.stream()

    async def _pump():
        async for frame in stream:
            frames.append(frame)
            if len(frames) >= count:
                return

    try:
        await asyncio.wait_for(_pump(), timeout=timeout)
    finally:
        await stream.aclose()
    return frames


async def test_stream_opens_with_a_connected_frame():
    """The UI shows a live indicator immediately, before anything happens."""
    hub = SseHub()
    frames = await read_frames(hub, 1)

    assert frames[0].startswith("event: connected")


async def test_broadcast_reaches_a_connected_client():
    hub = SseHub()
    frames: list[str] = []
    stream = hub.stream()

    async def _pump():
        async for frame in stream:
            frames.append(frame)
            if len(frames) >= 2:
                return

    task = asyncio.create_task(_pump())
    await asyncio.sleep(0.05)  # let the stream register its queue

    hub.broadcast("dyslexic.email.sent", {"contact_id": "abc", "kind": "initial"})

    try:
        await asyncio.wait_for(task, timeout=2.0)
    finally:
        await stream.aclose()

    assert "event: dyslexic.email.sent" in frames[1]
    payload = json.loads(frames[1].split("data: ", 1)[1].strip())
    assert payload["contact_id"] == "abc"


async def test_disconnect_removes_the_subscriber():
    """A dropped tab must not leak a queue that the hub keeps filling forever."""
    hub = SseHub()
    stream = hub.stream()

    await stream.__anext__()  # connected frame; queue is registered
    assert hub.subscriber_count == 1

    await stream.aclose()
    assert hub.subscriber_count == 0


async def test_slow_client_drops_oldest_events_instead_of_growing():
    """
    A backgrounded tab stops reading. The queue is bounded and drops the oldest
    event, because these are change notifications — the client refetches on
    reconnect anyway.
    """
    hub = SseHub()
    stream = hub.stream()
    await stream.__anext__()

    for index in range(MAX_QUEUED_EVENTS + 50):
        hub.broadcast("dyslexic.company.created", {"n": index})

    queue = next(iter(hub._subscribers))
    assert queue.qsize() <= MAX_QUEUED_EVENTS

    # The newest event survived; the oldest did not.
    remaining = [queue.get_nowait() for _ in range(queue.qsize())]
    assert remaining[-1]["payload"]["n"] == MAX_QUEUED_EVENTS + 49
    assert remaining[0]["payload"]["n"] > 0

    await stream.aclose()


async def test_redis_echo_is_not_delivered_twice():
    """
    EventBus.publish dispatches locally *and* republishes to Redis, whose
    listener on this same node dispatches it again. Caught in a live smoke
    test: every browser saw each change twice.
    """
    hub = SseHub()
    stream = hub.stream()
    await stream.__anext__()

    payload = {"company_id": "abc", "name": "Swiggy"}
    hub.broadcast("dyslexic.company.created", payload)
    hub.broadcast("dyslexic.company.created", dict(payload))  # the Redis echo

    queue = next(iter(hub._subscribers))
    assert queue.qsize() == 1

    await stream.aclose()


async def test_distinct_events_are_both_delivered():
    """De-duplication must not swallow two genuinely different changes."""
    hub = SseHub()
    stream = hub.stream()
    await stream.__anext__()

    hub.broadcast("dyslexic.company.created", {"company_id": "one"})
    hub.broadcast("dyslexic.company.created", {"company_id": "two"})

    queue = next(iter(hub._subscribers))
    assert queue.qsize() == 2

    await stream.aclose()


async def test_the_same_change_later_is_delivered_again(monkeypatch):
    """
    The window only covers the local/Redis echo gap. A contact genuinely
    claimed, released, then re-claimed produces an identical payload and must
    still notify — so de-duplication is time-bounded, not count-bounded.
    """
    hub = SseHub()
    stream = hub.stream()
    await stream.__anext__()

    hub.broadcast("dyslexic.contact.claimed", {"contact_id": "abc"})

    # Jump past the dedupe window rather than sleeping through it.
    real_monotonic = time.monotonic
    monkeypatch.setattr(
        time, "monotonic", lambda: real_monotonic() + DEDUPE_SECONDS + 1
    )
    hub.broadcast("dyslexic.contact.claimed", {"contact_id": "abc"})

    queue = next(iter(hub._subscribers))
    seen = [queue.get_nowait() for _ in range(queue.qsize())]
    claims = [event for event in seen if event["type"] == "dyslexic.contact.claimed"]
    assert len(claims) == 2

    await stream.aclose()


async def test_dedupe_map_stays_bounded():
    """A burst of distinct events must not grow the fingerprint map forever."""
    hub = SseHub()

    for index in range(DEDUPE_MAX_ENTRIES * 3):
        hub.broadcast("dyslexic.company.updated", {"n": index})

    assert len(hub._recent) <= DEDUPE_MAX_ENTRIES + 1


async def test_broadcast_with_no_clients_is_harmless():
    hub = SseHub()
    hub.broadcast("dyslexic.company.created", {"id": "x"})
    assert hub.subscriber_count == 0


async def test_every_client_receives_the_same_event():
    hub = SseHub()
    first, second = hub.stream(), hub.stream()
    await first.__anext__()
    await second.__anext__()

    hub.broadcast("dyslexic.outcome.recorded", {"outcome": "replied"})

    frame_one = await asyncio.wait_for(first.__anext__(), timeout=2.0)
    frame_two = await asyncio.wait_for(second.__anext__(), timeout=2.0)

    assert "dyslexic.outcome.recorded" in frame_one
    assert "dyslexic.outcome.recorded" in frame_two

    await first.aclose()
    await second.aclose()


async def test_wiring_is_idempotent():
    """
    Every connection wires the hub, because the bus has no unsubscribe and the
    hub outlives any one client. Wiring twice must not double-deliver.
    """
    hub = SseHub()
    hub.wire(["dyslexic.company.created"])
    hub.wire(["dyslexic.company.created"])

    assert hub._wired == {"dyslexic.company.created"}


async def test_heartbeat_interval_stays_under_common_proxy_timeouts():
    """
    Heartbeats are what stop an idle connection being closed by something in
    the middle. Sixty seconds is the usual default; stay well under it.
    """
    assert HEARTBEAT_SECONDS < 60

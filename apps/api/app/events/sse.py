"""
Server-sent events bridge.

The event bus already fans changes across nodes over Redis, but nothing carried
them to the browser. This hub subscribes once per event type and fans out to a
queue per connected client, which a streaming endpoint drains as SSE frames.

Generic on purpose — nothing here is Dyslexic-specific.

Each subscriber has a bounded queue. A browser tab that stops reading (laptop
asleep, tab backgrounded) must not grow a queue without limit, so the oldest
event is dropped when one fills. Dropping is safe because these payloads are
change notifications, not data — the client refetches whatever the event
touched, and a reconnect refetches everything.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from app.events.bus import event_bus

logger = logging.getLogger(__name__)

# Roughly a burst of activity from a busy working session. Past this, a client
# is not keeping up and old events have no value.
MAX_QUEUED_EVENTS = 100

# Long enough to stay quiet, short enough that intermediate proxies do not
# consider the connection idle and close it.
HEARTBEAT_SECONDS = 20


class SseHub:
    """Fans event-bus messages out to connected browsers."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._wired: set[str] = set()

    def wire(self, event_types: list[str]) -> None:
        """
        Subscribe to event types once, idempotently.

        Called on each connection, because the bus has no unsubscribe and the
        hub outlives any single client.
        """
        for event_type in event_types:
            if event_type in self._wired:
                continue
            event_bus.subscribe(event_type, self._make_handler(event_type))
            self._wired.add(event_type)

    def _make_handler(self, event_type: str):
        async def handler(payload: dict[str, Any]) -> None:
            self.broadcast(event_type, payload)

        return handler

    def broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        """Hand one event to every connected client."""
        message = {"type": event_type, "payload": payload}
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                # Drop the oldest rather than the newest — a stale notification
                # is worth less than a current one.
                try:
                    queue.get_nowait()
                    queue.put_nowait(message)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    logger.debug("Dropped an SSE event for a slow client")

    async def stream(self) -> AsyncIterator[str]:
        """
        Yield SSE frames for one client until it disconnects.

        The queue is registered on entry and removed in a `finally`, so a
        dropped connection cannot leak one.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUED_EVENTS)
        self._subscribers.add(queue)

        try:
            # Tell the client it is connected before anything happens, so the UI
            # can show a live indicator immediately.
            yield 'event: connected\ndata: {"ok": true}\n\n'

            while True:
                try:
                    message = await asyncio.wait_for(
                        queue.get(), timeout=HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                yield f"event: {message['type']}\ndata: {json.dumps(message['payload'])}\n\n"
        except asyncio.CancelledError:
            raise
        finally:
            self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


sse_hub = SseHub()

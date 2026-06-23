import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional
import redis.asyncio as aioredis

logger = logging.getLogger("event_bus")

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]]] = {}
        self.redis_url: Optional[str] = None
        self.redis: Optional[aioredis.Redis] = None
        self._pubsub_task: Optional[asyncio.Task] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None

    async def start(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url
        if self.redis_url:
            try:
                self.redis = aioredis.from_url(
                    self.redis_url, 
                    decode_responses=True,
                    health_check_interval=5,
                    socket_keepalive=True,
                    socket_timeout=60
                )
                await self.redis.ping()
                self._pubsub_task = asyncio.create_task(self._redis_listener())
                logger.info("EventBus connected to Redis pub/sub.")
            except Exception as e:
                logger.warning(f"EventBus failed to connect to Redis: {e}. Running in local-only mode.")
                if self.redis:
                    await self.redis.aclose()
                self.redis = None

    async def stop(self):
        """Gracefully shutdown the EventBus."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        
        if self._pubsub:
            await self._pubsub.close()

        if self.redis:
            await self.redis.aclose()  # Use aclose() for redis-py >= 5.0 in asyncio
            logger.info("EventBus disconnected from Redis.")

    async def _redis_listener(self):
        while self.redis:
            try:
                self._pubsub = self.redis.pubsub()
                await self._pubsub.subscribe("motherboard_events")
                async for message in self._pubsub.listen():
                    if message["type"] == "message":
                        try:
                            data = json.loads(message["data"])
                            await self._trigger_local(data["type"], data["payload"])
                        except json.JSONDecodeError:
                            logger.error("Failed to decode event message from Redis")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"EventBus Redis listener error: {e}. Reconnecting in 2s...")
                await asyncio.sleep(2)

    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        self._listeners[event_type].append(callback)

    async def publish(self, event_type: str, payload: Dict[str, Any]):
        event_data = {"type": event_type, "payload": payload}
        # Trigger local execution immediately
        await self._trigger_local(event_type, payload)
        
        # Push to Redis for cross-node instances
        if self.redis:
            try:
                await self.redis.publish("motherboard_events", json.dumps(event_data))
            except Exception as e:
                logger.error(f"Failed to publish event to Redis: {e}")

    async def _trigger_local(self, event_type: str, payload: Dict[str, Any]):
        callbacks = self._listeners.get(event_type, [])
        for cb in callbacks:
            try:
                # Fire and forget execution locally
                asyncio.create_task(cb(payload))
            except Exception as e:
                logger.error(f"Error executing subscriber callback for {event_type}: {e}")

event_bus = EventBus()

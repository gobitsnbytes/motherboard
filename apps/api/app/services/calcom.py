"""Small Cal.com API v2 adapter. Cal.com owns scheduling and notifications."""

from __future__ import annotations

from typing import Any

import httpx


class CalComError(RuntimeError):
    def __init__(self, code: str, *, status_code: int = 502, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class CalComClient:
    BASE_URL = "https://api.cal.com"
    EVENT_TYPES_VERSION = "2024-06-14"
    SLOTS_VERSION = "2024-09-04"
    BOOKINGS_VERSION = "2026-02-25"
    RESCHEDULE_VERSION = "2026-02-25"
    CANCEL_VERSION = "2026-02-25"
    LIST_BOOKINGS_VERSION = "2026-05-01"

    def __init__(self, api_key: str, *, client: httpx.AsyncClient | None = None):
        self._api_key = api_key
        self._client = client

    async def _request(
        self,
        method: str,
        path: str,
        *,
        version: str | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        if version:
            headers["cal-api-version"] = version
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url=self.BASE_URL, timeout=15.0)
        try:
            response = await client.request(method, path, headers=headers, params=params, json=json)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise CalComError("calcom_unavailable", retryable=True) from exc
        finally:
            if owns_client:
                await client.aclose()
        if response.status_code >= 400:
            retryable = response.status_code == 429 or response.status_code >= 500
            code = "calcom_rate_limited" if response.status_code == 429 else "calcom_request_failed"
            raise CalComError(code, status_code=503 if retryable else 502, retryable=retryable)
        try:
            body = response.json()
        except ValueError as exc:
            raise CalComError("calcom_invalid_response") from exc
        if isinstance(body, dict) and body.get("status") == "error":
            raise CalComError("calcom_request_failed")
        return body.get("data", body) if isinstance(body, dict) else body

    async def get_event_type(self, event_type_id: int) -> dict[str, Any]:
        return await self._request("GET", f"/v2/event-types/{event_type_id}", version=self.EVENT_TYPES_VERSION)

    async def get_me(self) -> dict[str, Any]:
        return await self._request("GET", "/v2/me", version=self.BOOKINGS_VERSION)

    async def get_slots(self, event_type_id: int, start: str, end: str, time_zone: str) -> Any:
        return await self._request(
            "GET",
            "/v2/slots",
            version=self.SLOTS_VERSION,
            params={
                "eventTypeId": event_type_id,
                "start": start,
                "end": end,
                "timeZone": time_zone,
                "format": "range",
            },
        )

    async def create_booking(
        self,
        *,
        event_type_id: int,
        start: str,
        attendee_name: str,
        attendee_email: str,
        attendee_time_zone: str,
        guests: list[str] | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "eventTypeId": event_type_id,
            "start": start,
            "attendee": {
                "name": attendee_name,
                "email": attendee_email,
                "timeZone": attendee_time_zone,
                "language": "en",
            },
            "metadata": metadata or {},
        }
        if guests:
            payload["guests"] = guests
        return await self._request("POST", "/v2/bookings", version=self.BOOKINGS_VERSION, json=payload)

    async def list_bookings(self, *, event_type_id: int, after_created_at: str) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            "/v2/bookings",
            version=self.LIST_BOOKINGS_VERSION,
            params={"eventTypeId": event_type_id, "afterCreatedAt": after_created_at, "limit": 50},
        )
        return data if isinstance(data, list) else []

    async def reschedule_booking(self, uid: str, *, start: str, reason: str | None = None) -> dict[str, Any]:
        payload = {"start": start}
        if reason:
            payload["reschedulingReason"] = reason
        return await self._request(
            "POST", f"/v2/bookings/{uid}/reschedule", version=self.RESCHEDULE_VERSION, json=payload
        )

    async def cancel_booking(self, uid: str, *, reason: str | None = None) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/v2/bookings/{uid}/cancel",
            version=self.CANCEL_VERSION,
            json={"cancellationReason": reason} if reason else {},
        )

    async def create_webhook(self, *, subscriber_url: str, secret: str, triggers: list[str]) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v2/webhooks",
            json={
                "subscriberUrl": subscriber_url,
                "triggers": triggers,
                "active": True,
                "secret": secret,
            },
        )

    async def delete_webhook(self, webhook_id: str) -> Any:
        return await self._request("DELETE", f"/v2/webhooks/{webhook_id}")

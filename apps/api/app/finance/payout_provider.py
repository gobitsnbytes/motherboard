"""RazorpayX payout provider seam — placeholder only.

This is deliberately separate from ``app.services.razorpayx_adapter`` (which
provisions paper VirtualAccount/VirtualCard identifiers). This module is the
narrow *payout* boundary: moving real money out via RazorpayX, checking a
real payout's status, reading the real account balance, and verifying
inbound webhooks. None of it makes a network call yet — every method raises
``RazorpayXNotConfigured`` (surfaced by the router as HTTP 503) until a real
integration is wired in.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings


class RazorpayXNotConfigured(RuntimeError):
    """Raised by every PayoutProvider method — RazorpayX payouts are not wired up yet."""


@dataclass(frozen=True)
class PayoutResult:
    payout_id: str
    status: str


@dataclass(frozen=True)
class PayoutStatus:
    payout_id: str
    status: str
    utr: str | None = None


@dataclass(frozen=True)
class BalanceResult:
    balance_paise: int
    currency: str = "INR"


class PayoutProvider(Protocol):
    """Narrow payout boundary a real banking provider must implement."""

    async def create_payout(
        self,
        *,
        account_number: str,
        ifsc: str,
        amount_paise: int,
        purpose: str,
        reference_id: str,
    ) -> PayoutResult: ...

    async def fetch_status(self, payout_id: str) -> PayoutStatus: ...

    async def fetch_balance(self) -> BalanceResult: ...

    def verify_webhook(self, payload: bytes, signature: str) -> bool: ...


class RazorpayXProvider:
    """Placeholder RazorpayX implementation. No network calls.

    Every payout/status/balance method raises ``RazorpayXNotConfigured`` —
    intentionally, regardless of whether API keys are present — because no
    real RazorpayX wiring exists yet; a deployment must never mistake this
    stub for live banking. ``verify_webhook`` is functional (HMAC-SHA256
    against a configured secret) so the webhook route can be exercised safely
    ahead of the rest of the integration.
    """

    def __init__(
        self, *, key_id: str | None, secret: str | None, webhook_secret: str | None
    ) -> None:
        self._key_id = key_id
        self._secret = secret
        self._webhook_secret = webhook_secret

    @property
    def is_configured(self) -> bool:
        return bool(self._key_id and self._secret)

    def _not_wired(self) -> RazorpayXNotConfigured:
        return RazorpayXNotConfigured(
            "RazorpayX payouts are not implemented yet. This is a placeholder seam "
            "(app.finance.payout_provider) — no network call was made. Wire the real "
            "RazorpayX Payouts API here before enabling live payouts."
        )

    async def create_payout(
        self,
        *,
        account_number: str,
        ifsc: str,
        amount_paise: int,
        purpose: str,
        reference_id: str,
    ) -> PayoutResult:
        raise self._not_wired()

    async def fetch_status(self, payout_id: str) -> PayoutStatus:
        raise self._not_wired()

    async def fetch_balance(self) -> BalanceResult:
        raise self._not_wired()

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """HMAC-SHA256 signature check, RazorpayX's documented scheme.

        Returns False (never raises) when no webhook secret is configured or
        the signature doesn't match — the router treats "not configured" and
        "invalid signature" as distinct rejections.
        """
        if not self._webhook_secret:
            return False
        expected = hmac.new(
            self._webhook_secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    @property
    def has_webhook_secret(self) -> bool:
        return bool(self._webhook_secret)


def build_payout_provider(settings: Settings) -> RazorpayXProvider:
    return RazorpayXProvider(
        key_id=settings.razorpayx_key_id,
        secret=settings.razorpayx_secret,
        webhook_secret=getattr(settings, "razorpayx_webhook_secret", None),
    )

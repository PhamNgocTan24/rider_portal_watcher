"""
Telegram notification service — optional, degrades gracefully.

If TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing, all methods
log once and return without raising.
"""
from __future__ import annotations

import structlog
import httpx

from app.config import settings

logger = structlog.get_logger()

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
_disabled_logged = False  # log disabled state only once per process


def _is_configured() -> bool:
    return bool(settings.telegram_bot_token and settings.telegram_chat_id)


async def _send(text: str) -> None:
    global _disabled_logged
    if not _is_configured():
        if not _disabled_logged:
            logger.info("telegram_disabled", reason="missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
            _disabled_logged = True
        return

    url = _TELEGRAM_API.format(token=settings.telegram_bot_token)
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                logger.warning("telegram_send_failed", status=resp.status_code, body=resp.text[:200])
            else:
                logger.info("telegram_sent", preview=text[:60])
    except Exception as exc:
        logger.warning("telegram_send_error", error=str(exc))


# ---------------------------------------------------------------------------
# Public notification functions
# ---------------------------------------------------------------------------

async def notify_new_booking(
    external_booking_id: str,
    portal_name: str,
    pickup: str | None,
    dropoff: str | None,
    value: float | None,
) -> None:
    val_str = f"£{value:.2f}" if value else "N/A"
    msg = (
        f"🚗 <b>New booking detected</b>\n"
        f"Portal: {portal_name}\n"
        f"ID: <code>{external_booking_id}</code>\n"
        f"From: {pickup or 'N/A'}\n"
        f"To: {dropoff or 'N/A'}\n"
        f"Value: {val_str}"
    )
    await _send(msg)


async def notify_booking_decision(
    external_booking_id: str,
    status: str,
    reason: str | None,
) -> None:
    emoji = {"accepted_candidate": "✅", "auto_accepted": "🤖", "rejected": "❌"}.get(status, "ℹ️")
    msg = (
        f"{emoji} <b>Booking decision: {status}</b>\n"
        f"ID: <code>{external_booking_id}</code>\n"
        f"Reason: {reason or 'N/A'}"
    )
    await _send(msg)


async def notify_automation_error(
    portal_name: str,
    step: str,
    message: str,
    external_booking_id: str | None = None,
) -> None:
    booking_part = f"\nBooking: <code>{external_booking_id}</code>" if external_booking_id else ""
    msg = (
        f"🔴 <b>Automation error</b>\n"
        f"Portal: {portal_name}\n"
        f"Step: {step}{booking_part}\n"
        f"Detail: {message[:300]}"
    )
    await _send(msg)


async def notify_portal_degraded(portal_name: str, reason: str) -> None:
    msg = (
        f"⚠️ <b>Portal degraded</b>\n"
        f"Portal: {portal_name}\n"
        f"Reason: {reason[:300]}\n"
        f"Auto-accept is now paused."
    )
    await _send(msg)

"""Daily AI limits shared by every AI tool (Captions, CV Generator writing help, ...).

Each tool has its own per-guest / per-user daily limit; all tools together share one site-wide
daily limit, so the AI's free quota is never used up. A try is reserved BEFORE the AI call (so
many requests at once can't go over a limit) and given back if the AI fails:

    reservation = ai_quota.reserve("cv_writer", requester, limit)   # may raise QuotaError
    try:
        ... call the AI ...
    except AIError:
        ai_quota.refund(requester, reservation)
        raise

Tool names must also be listed in 20261014_ai_tries.sql (`tool in (...)`).
"""
import logging
from dataclasses import dataclass
from typing import Optional

from flask import current_app

from app.services.ai_quota_repository import QuotaUnavailable, SupabaseAIQuotaRepository, get_repository

logger = logging.getLogger(__name__)

TOOLS = ("captions", "cv_writer")


@dataclass(frozen=True)
class Requester:
    """Who is asking. access_token is None for a guest, who is counted by ip_hash instead."""
    ip_hash: str
    access_token: Optional[str] = None

    @property
    def is_guest(self):
        return not self.access_token


@dataclass(frozen=True)
class Reservation:
    try_id: Optional[str]
    used: int    # tries used today, including this one
    limit: int

    @property
    def remaining(self):
        return max(self.limit - self.used, 0)


class QuotaError(Exception):
    """code: "limit" (this guest/user is done for today), "site_limit" (everyone is) or
    "unavailable" (tries can't be counted right now)."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def init_ai_quota(app):
    app.extensions["ai_quota_repository"] = SupabaseAIQuotaRepository()


def reserve(tool, requester, limit):
    _check_tool(tool)
    try:
        result = get_repository().consume_try(
            requester.access_token, tool, requester.ip_hash, limit, current_app.config["AI_SITE_DAILY_LIMIT"]
        ) or {}
    except QuotaUnavailable:
        raise QuotaError("unavailable") from None
    status = result.get("status")
    if status == "limit":
        raise QuotaError("limit")
    if status == "site_limit":
        logger.warning("AI site-wide daily limit reached (asked by %s)", tool)
        raise QuotaError("site_limit")
    if status != "ok":
        logger.error("Unexpected consume_ai_try result: %r", result)
        raise QuotaError("unavailable")
    return Reservation(try_id=result.get("try_id"), used=int(result.get("used") or 0), limit=limit)


def refund(requester, reservation):
    """Give the try back (the AI failed). Never raises: the user already sees the AI error."""
    if not reservation or not reservation.try_id:
        return
    try:
        get_repository().refund_try(requester.access_token, reservation.try_id)
    except QuotaUnavailable:
        logger.warning("Could not give back AI try %s", reservation.try_id)


def tries_used(tool, requester):
    _check_tool(tool)
    try:
        return get_repository().tries_used(requester.access_token, tool, requester.ip_hash)
    except QuotaUnavailable:
        raise QuotaError("unavailable") from None


def _check_tool(tool):
    if tool not in TOOLS:
        raise ValueError(f"Unknown AI tool '{tool}'. Add it to ai_quota.TOOLS and 20261014_ai_tries.sql.")

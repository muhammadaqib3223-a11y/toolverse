"""Business rules for captions: validation, daily limits, the AI call and history.

Routes call these functions and never see the repository or the AI provider directly, so tests
can swap in fakes (tests/fakes.py) and never call Supabase or Gemini.

A try is reserved BEFORE the AI call (so many requests at once can't go over the limit) and
given back if the AI fails, so a guest never loses one of their few tries to an outage.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

from flask import current_app

from app.blueprints.tools.captions.errors import CaptionError, CaptionNotFound, CaptionsUnavailable
from app.blueprints.tools.captions.prompts import CAPTION_COUNT, SCHEMA, SYSTEM, build_prompt
from app.blueprints.tools.captions.repository import get_repository
from app.services.ai import AIError, AIUnavailable, get_ai_provider

logger = logging.getLogger(__name__)

PLATFORMS = ("instagram", "linkedin")
TOPIC_MAX_LENGTH = 500
CAPTION_MAX_LENGTH = 3000
HISTORY_LIMIT = 20

_ID_RE = re.compile(r"^[0-9a-fA-F-]{8,36}$")


@dataclass(frozen=True)
class Requester:
    """Who is asking. access_token is None for a guest, who is counted by ip_hash instead."""
    ip_hash: str
    access_token: Optional[str] = None

    @property
    def is_guest(self):
        return not self.access_token


def daily_limit(requester):
    config = current_app.config
    return config["CAPTIONS_GUEST_DAILY_LIMIT"] if requester.is_guest else config["CAPTIONS_USER_DAILY_LIMIT"]


def usage(requester):
    limit = daily_limit(requester)
    used = get_repository().tries_used(requester.access_token, requester.ip_hash)
    return {"limit": limit, "used": used, "remaining": max(limit - used, 0)}


def generate(requester, topic, platform):
    """Write captions. Returns {captions, topic, platform, saved (history row or None), limit, remaining}."""
    topic, platform = _validate(topic, platform)
    limit = daily_limit(requester)
    repo = get_repository()

    reservation = repo.consume_try(
        requester.access_token, requester.ip_hash, limit, current_app.config["CAPTIONS_SITE_DAILY_LIMIT"]
    ) or {}
    status = reservation.get("status")
    if status == "limit":
        raise CaptionError("limit_guest" if requester.is_guest else "limit_user")
    if status == "site_limit":
        logger.warning("Captions site-wide daily limit reached")
        raise CaptionError("site_limit")
    if status != "ok":
        logger.error("Unexpected consume_caption_try result: %r", reservation)
        raise CaptionsUnavailable()

    try:
        captions = _write_captions(topic, platform)
    except AIError as error:
        _refund(repo, requester, reservation.get("try_id"))
        raise CaptionError(error.code) from None

    saved = None
    if not requester.is_guest:
        try:
            saved = repo.insert_history(requester.access_token, topic, platform, captions)
        except CaptionsUnavailable:
            # The captions are still shown; only the history entry is missing.
            logger.warning("Captions written but not saved to history")

    used = int(reservation.get("used") or 0)
    return {
        "captions": captions,
        "topic": topic,
        "platform": platform,
        "saved": saved,
        "limit": limit,
        "remaining": max(limit - used, 0),
    }


def list_history(access_token):
    return get_repository().list_history(access_token, HISTORY_LIMIT)


def delete_history(access_token, caption_id):
    if not caption_id or not _ID_RE.match(str(caption_id)):
        raise CaptionNotFound()
    if not get_repository().delete_history(access_token, caption_id):
        raise CaptionNotFound()


def _write_captions(topic, platform):
    result = get_ai_provider().generate_json(system=SYSTEM, prompt=build_prompt(topic, platform), schema=SCHEMA)
    raw = result.get("captions") if isinstance(result, dict) else None
    captions = []
    for item in raw if isinstance(raw, list) else []:
        text = item.strip() if isinstance(item, str) else ""
        if text and text not in captions:
            captions.append(text[:CAPTION_MAX_LENGTH])
    if not captions:
        logger.warning("AI returned no usable captions: %.200r", result)
        raise AIUnavailable("no_captions")
    return captions[:CAPTION_COUNT]


def _refund(repo, requester, try_id):
    if not try_id:
        return
    try:
        repo.refund_try(requester.access_token, try_id)
    except CaptionsUnavailable:
        logger.warning("Could not give back caption try %s", try_id)


def _validate(topic, platform):
    topic = (topic if isinstance(topic, str) else "").strip()
    if not topic:
        raise CaptionError("topic_required")
    if len(topic) > TOPIC_MAX_LENGTH:
        raise CaptionError("topic_too_long")
    platform = (platform if isinstance(platform, str) else "").strip().lower()
    if platform not in PLATFORMS:
        raise CaptionError("platform_invalid")
    return topic, platform

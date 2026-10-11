"""AI writing help for the CV Generator ("Improve with AI").

The user writes simply (English, Roman Urdu or Urdu); the AI suggests professional, ATS-friendly
English for one section (summary, one job, skills) or the whole CV. Nothing is changed here:
the page shows the suggestion and the user accepts, edits or discards it.

Keeping the AI honest takes more than the prompt (prompts.py), so every answer is checked:
  * a number the user never wrote (a new "40%" or "5 years") removes that sentence/bullet;
  * a skill must quote (`source`) words that really are in the CV, or it is dropped;
  * jobs the user left without a description get no invented bullets.
Contact details (email, phone, website) and the name are never sent to the AI.

Daily limits use the shared AI limit system (app/services/ai_quota.py), tool "cv_writer":
a try is reserved before the AI call and given back if the AI fails or gives nothing usable.
"""
import logging
import re

from flask import current_app

from app.blueprints.tools.cv_generator import prompts, services
from app.blueprints.tools.cv_generator.errors import CVError
from app.services import ai_quota
from app.services.ai import AIError, get_ai_provider
from app.services.ai_quota import QuotaError

logger = logging.getLogger(__name__)

AI_TOOL = "cv_writer"
SECTIONS = ("summary", "experience", "skills", "all")
# Low temperature: careful rewording, not creative writing.
TEMPERATURE = 0.4
MAX_BULLETS = 8
BULLET_MAX_LENGTH = 300
MAX_AI_SKILLS = 25

_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_NUMBER_WORDS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
    "fifteen": "15", "twenty": "20", "thirty": "30", "fifty": "50", "hundred": "100",
}
_WORD_RE = re.compile(r"[a-z]+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_BULLET_START_RE = re.compile(r"^[\s\-•*–·]+")


class _NothingUsable(Exception):
    """The AI answered, but nothing in the answer passed the checks."""


def daily_limit(requester):
    config = current_app.config
    return config["CV_AI_GUEST_DAILY_LIMIT"] if requester.is_guest else config["CV_AI_USER_DAILY_LIMIT"]


def usage(requester):
    limit = daily_limit(requester)
    try:
        used = ai_quota.tries_used(AI_TOOL, requester)
    except QuotaError:
        raise CVError("ai_unavailable") from None
    return {"limit": limit, "used": used, "remaining": max(limit - used, 0)}


def improve(requester, section, raw_cv, index=None):
    """A suggestion for `section` ("summary" | "experience" | "skills" | "all").
    For "experience", `index` is the job's position in the form.
    Returns {section, suggestion, removed, limit, remaining}; `removed` counts sentences or
    bullets taken out because they had numbers the user never wrote."""
    if section not in SECTIONS:
        raise CVError("section_invalid", "section")
    cv, jobs = _read_cv(raw_cv)
    job_index, job = _pick_job(raw_cv, index) if section == "experience" else (None, None)
    _check_enough(section, cv, job)

    cv_text = _cv_text(cv)
    allowed = _numbers(cv_text)
    prompt = prompts.build_prompt(section, cv_text, _job_text(job) if job else "")

    limit = daily_limit(requester)
    reservation = _reserve(requester, limit)
    try:
        result = get_ai_provider().generate_json(
            system=prompts.SYSTEM, prompt=prompt, schema=prompts.SCHEMAS[section],
            temperature=TEMPERATURE, max_output_tokens=4096 if section == "all" else 2048,
        )
        checker = _Checker(allowed, cv_text)
        suggestion = _clean(section, result, checker, jobs, job_index)
    except AIError as error:
        ai_quota.refund(requester, reservation)
        raise CVError(error.code) from None
    except _NothingUsable:
        logger.warning("CV AI answer had nothing usable for %s: %.300r", section, result)
        ai_quota.refund(requester, reservation)
        raise CVError("ai_unavailable") from None

    return {
        "section": section,
        "suggestion": suggestion,
        "removed": checker.removed,
        "limit": limit,
        "remaining": reservation.remaining,
    }


# ── Reading the CV ───────────────────────────────────────────────────────────

def _read_cv(raw_cv):
    """The cleaned CV without contact details, plus [(form index, job)] for jobs with content."""
    if not isinstance(raw_cv, dict):
        raise CVError("invalid_data")
    personal = raw_cv.get("personal") if isinstance(raw_cv.get("personal"), dict) else {}
    # Contact details are not needed to write better text, so they never reach the AI.
    private = {"full_name", "email", "phone", "website", "linkedin"}
    safe = dict(raw_cv, personal={key: value for key, value in personal.items() if key not in private})
    cv = services.parse_cv(safe, require_name=False)
    raw_jobs = raw_cv.get("experience") if isinstance(raw_cv.get("experience"), list) else []
    jobs = []
    for position, item in enumerate(raw_jobs[:services.MAX_EXPERIENCE]):
        job = services.parse_job(item, position)
        if services.job_has_content(job):
            jobs.append((position, job))
    return cv, jobs


def _pick_job(raw_cv, index):
    raw_jobs = raw_cv.get("experience") if isinstance(raw_cv.get("experience"), list) else []
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(raw_jobs):
        raise CVError("invalid_data", "index")
    return index, services.parse_job(raw_jobs[index], index)


def _check_enough(section, cv, job):
    if section == "experience":
        enough = bool(job.description)
    elif section == "summary":
        enough = bool(cv.summary or cv.personal.headline or cv.experience or cv.education)
    elif section == "skills":
        enough = bool(cv.skills or cv.summary or any(job.description for job in cv.experience))
    else:
        enough = bool(cv.summary or cv.experience or cv.skills or cv.education)
    if not enough:
        raise CVError("nothing_to_improve", section)


def _cv_text(cv):
    lines = []
    if cv.personal.headline:
        lines.append(f"Headline: {cv.personal.headline}")
    if cv.personal.location:
        lines.append(f"Location: {cv.personal.location}")
    if cv.summary:
        lines += ["Summary:", cv.summary]
    if cv.experience:
        lines.append("Experience:")
        for number, job in enumerate(cv.experience, 1):
            lines.append(f"{number}. {_job_text(job)}")
    if cv.education:
        lines.append("Education:")
        for number, item in enumerate(cv.education, 1):
            dates = " - ".join(part for part in (item.start, item.end) if part)
            head = " | ".join(part for part in (item.degree, item.school, item.location, dates) if part)
            lines.append(f"{number}. {head}" + (f"\n   {item.description}" if item.description else ""))
    if cv.skills:
        lines.append("Skills: " + ", ".join(cv.skills))
    return "\n".join(lines)


def _job_text(job):
    end = "now (current job)" if job.current else job.end
    dates = " - ".join(part for part in (job.start, end) if part)
    head = " | ".join(part for part in (
        f"Job title: {job.job_title}" if job.job_title else "",
        f"Company: {job.company}" if job.company else "",
        job.location,
        f"Dates: {dates}" if dates else "",
    ) if part)
    description = job.description or "(no description)"
    return f"{head}\n   What they did: {description}"


# ── Limits ───────────────────────────────────────────────────────────────────

def _reserve(requester, limit):
    try:
        return ai_quota.reserve(AI_TOOL, requester, limit)
    except QuotaError as error:
        if error.code == "limit":
            raise CVError("limit_guest" if requester.is_guest else "limit_user") from None
        if error.code == "site_limit":
            raise CVError("site_limit") from None
        raise CVError("ai_unavailable") from None


# ── Checking the AI's answer ─────────────────────────────────────────────────

def _numbers(text):
    """Every number in `text` (digits, and common English number words as digits)."""
    found = {match.replace(",", "") for match in _NUMBER_RE.findall(text)}
    found |= {_NUMBER_WORDS[word] for word in _WORD_RE.findall(text.lower()) if word in _NUMBER_WORDS}
    return found


def _normalise(text):
    return " ".join(text.casefold().split())


class _Checker:
    def __init__(self, allowed_numbers, cv_text):
        self.allowed = allowed_numbers
        self.cv_text = _normalise(cv_text)
        self.removed = 0

    def honest(self, text):
        """False (and counted) if `text` has a number the user never wrote."""
        if _numbers(text) - self.allowed:
            self.removed += 1
            return False
        return True

    def grounded(self, source):
        source = _normalise(source)
        return bool(source) and source in self.cv_text


def _clean(section, result, checker, jobs, job_index):
    if not isinstance(result, dict):
        raise _NothingUsable()
    if section == "summary":
        summary = _clean_summary(result.get("summary"), checker)
        if not summary:
            raise _NothingUsable()
        return {"summary": summary}
    if section == "experience":
        description = _clean_bullets(result.get("bullets"), checker)
        if not description:
            raise _NothingUsable()
        return {"index": job_index, "description": description}
    if section == "skills":
        skills = _clean_skills(result.get("skills"), checker)
        if not skills:
            raise _NothingUsable()
        return {"skills": skills}

    suggestion = {
        "headline": _clean_headline(result.get("headline"), checker),
        "summary": _clean_summary(result.get("summary"), checker),
        "experience": _clean_jobs(result.get("experience"), checker, jobs),
        "skills": _clean_skills(result.get("skills"), checker),
    }
    if not any(suggestion.values()):
        raise _NothingUsable()
    return suggestion


def _clean_summary(raw, checker):
    if not isinstance(raw, str):
        return ""
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(" ".join(raw.split())) if s.strip()]
    summary = " ".join(s for s in sentences if checker.honest(s))
    return summary[:services.LIMITS["summary"]].strip()


def _clean_headline(raw, checker):
    if not isinstance(raw, str):
        return ""
    headline = " ".join(raw.split()).strip(" .")
    if not headline or len(headline) > services.LIMITS["headline"] or not checker.honest(headline):
        return ""
    return headline


def _clean_bullets(raw, checker):
    """Bullets as the form's description text ("- one\\n- two"), within the field's limit."""
    if not isinstance(raw, list):
        return ""
    lines = []
    for item in raw[:MAX_BULLETS]:
        if not isinstance(item, str):
            continue
        text = " ".join(_BULLET_START_RE.sub("", item).split())
        if not text or not checker.honest(text):
            continue
        line = "- " + text[:BULLET_MAX_LENGTH]
        if len("\n".join(lines + [line])) > services.LIMITS["description"]:
            break
        lines.append(line)
    return "\n".join(lines)


def _clean_jobs(raw, checker, jobs):
    """[{index, description}] for jobs that had a description, matched to the form by position."""
    if not isinstance(raw, list) or len(raw) != len(jobs):
        return []
    cleaned = []
    for (form_index, job), item in zip(jobs, raw):
        if not job.description or not isinstance(item, dict):
            continue  # no notes from the user = nothing to rewrite (and nothing to invent)
        description = _clean_bullets(item.get("bullets"), checker)
        if description:
            cleaned.append({"index": form_index, "description": description})
    return cleaned


def _clean_skills(raw, checker):
    if not isinstance(raw, list):
        return []
    skills, seen = [], set()
    for item in raw[:MAX_AI_SKILLS]:
        if not isinstance(item, dict):
            continue
        name = " ".join(str(item.get("name") or "").split())
        source = str(item.get("source") or "")
        if not name or len(name) > services.LIMITS["skill"] or name.casefold() in seen:
            continue
        if not checker.grounded(source) or not checker.honest(name):
            continue
        seen.add(name.casefold())
        skills.append(name)
    return skills[:services.MAX_SKILLS]

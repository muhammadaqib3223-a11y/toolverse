"""Business rules for the CV Generator: check and clean the form data, then build the PDF.

No Supabase here (part A saves nothing). The PDF layouts live in pdf_templates/, the shared PDF
setup (fonts, Urdu shaping) in app/services/pdf_builder.py.
"""
import re
import unicodedata
from dataclasses import dataclass, field

from flask_babel import force_locale
from flask_babel import gettext as _

from app.blueprints.tools.cv_generator.errors import CVError
from app.blueprints.tools.cv_generator.pdf_templates import render_cv
from app.services.pdf_builder import PdfBuildError

TEMPLATES = ("classic", "modern")
LANGUAGES = ("en", "ur")

MAX_EXPERIENCE = 15
MAX_EDUCATION = 10
MAX_SKILLS = 40

# Max characters per field. The form uses the same numbers (maxlength), so normal users never
# hit these; they stop oversized requests.
LIMITS = {
    "full_name": 100,
    "headline": 120,
    "email": 254,
    "phone": 40,
    "location": 100,
    "website": 200,
    "summary": 2000,
    "job_title": 120,
    "company": 120,
    "degree": 160,
    "school": 160,
    "date": 30,
    "description": 2000,
    "skill": 60,
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_WEBSITE_RE = re.compile(r"^(https?://)?[\w.-]+\.[a-z]{2,}(/\S*)?$", re.IGNORECASE)
_MANY_BLANK_LINES_RE = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class Personal:
    full_name: str
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""

    @property
    def website_url(self):
        """A clickable https link for the website, or "" if there is none."""
        if not self.website:
            return ""
        return self.website if re.match(r"^https?://", self.website, re.I) else "https://" + self.website


@dataclass(frozen=True)
class Experience:
    job_title: str = ""
    company: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    current: bool = False
    description: str = ""


@dataclass(frozen=True)
class Education:
    degree: str = ""
    school: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    description: str = ""


@dataclass(frozen=True)
class CV:
    personal: Personal
    summary: str = ""
    experience: tuple = field(default_factory=tuple)
    education: tuple = field(default_factory=tuple)
    skills: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class PdfFile:
    content: bytes
    filename: str


def build_pdf(data, template, language):
    """Check the form data and turn it into a PDF. Raises CVError for anything the user can fix."""
    if template not in TEMPLATES:
        raise CVError("template_invalid", "template")
    if language not in LANGUAGES:
        raise CVError("language_invalid", "language")
    cv = parse_cv(data)
    try:
        content = render_cv(template, cv, labels(language), rtl=language == "ur", language=language)
    except PdfBuildError as error:
        raise CVError("pdf_failed") from error
    return PdfFile(content=content, filename=pdf_filename(cv.personal.full_name))


def parse_cv(data):
    """A clean CV from the raw JSON the form sends. Empty jobs/education rows are dropped."""
    if not isinstance(data, dict):
        raise CVError("invalid_data")
    personal = _dict(data.get("personal"))
    full_name = _text(personal, "full_name", "personal.full_name", LIMITS["full_name"])
    if not full_name:
        raise CVError("name_required", "personal.full_name")
    email = _text(personal, "email", "personal.email", LIMITS["email"])
    if email and not _EMAIL_RE.match(email):
        raise CVError("email_invalid", "personal.email")
    website = _text(personal, "website", "personal.website", LIMITS["website"])
    if website and not _WEBSITE_RE.match(website):
        raise CVError("website_invalid", "personal.website")

    return CV(
        personal=Personal(
            full_name=full_name,
            headline=_text(personal, "headline", "personal.headline", LIMITS["headline"]),
            email=email,
            phone=_text(personal, "phone", "personal.phone", LIMITS["phone"]),
            location=_text(personal, "location", "personal.location", LIMITS["location"]),
            website=website,
        ),
        summary=_text(data, "summary", "summary", LIMITS["summary"], multiline=True),
        experience=_parse_experience(data.get("experience")),
        education=_parse_education(data.get("education")),
        skills=_parse_skills(data.get("skills")),
    )


def labels(language):
    """Section headings and small words, translated into the CV's language (not the page's)."""
    with force_locale(language):
        return {
            "summary": _("Summary"),
            "experience": _("Experience"),
            "education": _("Education"),
            "skills": _("Skills"),
            "contact": _("Contact"),
            "present": _("Present"),
        }


def pdf_filename(full_name):
    """e.g. "Sara_Khan_CV.pdf". Non-Latin names keep their letters; the route also sends an ASCII copy."""
    words = re.findall(r"\w+", full_name)
    stem = "_".join(words)[:60].strip("_")
    return f"{stem}_CV.pdf" if stem else "CV.pdf"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_experience(raw):
    items = _list(raw)
    if len(items) > MAX_EXPERIENCE:
        raise CVError("too_many_experience", "experience")
    jobs = []
    for index, item in enumerate(items):
        item = _dict(item)
        prefix = f"experience.{index}."
        job = Experience(
            job_title=_text(item, "job_title", prefix + "job_title", LIMITS["job_title"]),
            company=_text(item, "company", prefix + "company", LIMITS["company"]),
            location=_text(item, "location", prefix + "location", LIMITS["location"]),
            start=_text(item, "start", prefix + "start", LIMITS["date"]),
            end=_text(item, "end", prefix + "end", LIMITS["date"]),
            current=item.get("current") is True,
            description=_text(item, "description", prefix + "description", LIMITS["description"], multiline=True),
        )
        if job.job_title or job.company or job.description:
            jobs.append(job)
    return tuple(jobs)


def _parse_education(raw):
    items = _list(raw)
    if len(items) > MAX_EDUCATION:
        raise CVError("too_many_education", "education")
    entries = []
    for index, item in enumerate(items):
        item = _dict(item)
        prefix = f"education.{index}."
        entry = Education(
            degree=_text(item, "degree", prefix + "degree", LIMITS["degree"]),
            school=_text(item, "school", prefix + "school", LIMITS["school"]),
            location=_text(item, "location", prefix + "location", LIMITS["location"]),
            start=_text(item, "start", prefix + "start", LIMITS["date"]),
            end=_text(item, "end", prefix + "end", LIMITS["date"]),
            description=_text(item, "description", prefix + "description", LIMITS["description"], multiline=True),
        )
        if entry.degree or entry.school or entry.description:
            entries.append(entry)
    return tuple(entries)


def _parse_skills(raw):
    items = _list(raw)
    if len(items) > MAX_SKILLS:
        raise CVError("too_many_skills", "skills")
    skills = []
    seen = set()
    for item in items:
        if not isinstance(item, str):
            raise CVError("invalid_data", "skills")
        skill = _clean(item)
        if len(skill) > LIMITS["skill"]:
            raise CVError("too_long", "skills")
        if skill and skill.casefold() not in seen:
            seen.add(skill.casefold())
            skills.append(skill)
    return tuple(skills)


def _dict(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CVError("invalid_data")
    return value


def _list(value):
    if value is None:
        return []
    if not isinstance(value, list):
        raise CVError("invalid_data")
    return value


def _text(source, key, field_path, max_length, multiline=False):
    value = source.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise CVError("invalid_data", field_path)
    value = _clean(value, multiline=multiline)
    if len(value) > max_length:
        raise CVError("too_long", field_path)
    return value


def _clean(value, multiline=False):
    """Trim, drop invisible control characters, and keep line breaks only where they belong."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    kept = []
    for char in value:
        if char == "\n":
            kept.append("\n" if multiline else " ")
        elif char == "\t":
            kept.append(" ")
        elif unicodedata.category(char) != "Cc":
            kept.append(char)
    value = "".join(kept)
    if multiline:
        lines = [line.strip() for line in value.split("\n")]
        return _MANY_BLANK_LINES_RE.sub("\n\n", "\n".join(lines)).strip()
    return " ".join(value.split())

"""Business rules for the CV Generator: check and clean the form data, then build the PDF.

No Supabase here: saving CVs is saved_cvs.py (which uses this file's cleaning rules). The PDF
layouts live in pdf_templates/, the shared PDF setup (fonts, Urdu shaping) in
app/services/pdf_builder.py, photo checks in app/services/photos.py.

Every section except the name is optional; an empty section never appears in the PDF.
"""
import re
import unicodedata
from dataclasses import asdict, dataclass, field

from flask_babel import force_locale
from flask_babel import gettext as _

from app.blueprints.tools.cv_generator.errors import CVError
from app.blueprints.tools.cv_generator.pdf_templates import ACCENTS, DEFAULT_ACCENT, LAYOUTS, render_cv
from app.services import photos
from app.services.pdf_builder import PdfBuildError

TEMPLATES = tuple(LAYOUTS)
DEFAULT_TEMPLATE = TEMPLATES[0]
ACCENT_NAMES = tuple(ACCENTS)
LANGUAGES = ("en", "ur")
LANGUAGE_LEVELS = ("native", "fluent", "advanced", "intermediate", "basic")

MAX_EXPERIENCE = 15
MAX_EDUCATION = 10
MAX_SKILLS = 40
MAX_PROJECTS = 10
MAX_CERTIFICATIONS = 15
MAX_LANGUAGES = 10
MAX_HOBBIES = 15
MAX_REFERENCES = 4

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
    "language": 40,
    "certificate": 160,
    "issuer": 120,
    "project": 120,
    "hobby": 40,
    "reference_name": 100,
    "reference_title": 120,
    "reference_contact": 120,
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_WEBSITE_RE = re.compile(r"^(https?://)?[\w.-]+\.[a-z]{2,}(/\S*)?$", re.IGNORECASE)
_MANY_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _as_link(address):
    """A clickable https link for a web address, or "" if there is none."""
    if not address:
        return ""
    return address if re.match(r"^https?://", address, re.I) else "https://" + address


@dataclass(frozen=True)
class Personal:
    full_name: str
    headline: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    linkedin: str = ""

    @property
    def website_url(self):
        return _as_link(self.website)

    @property
    def linkedin_url(self):
        return _as_link(self.linkedin)


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
class Project:
    name: str = ""
    link: str = ""
    description: str = ""

    @property
    def link_url(self):
        return _as_link(self.link)


@dataclass(frozen=True)
class Certification:
    name: str = ""
    issuer: str = ""
    date: str = ""


@dataclass(frozen=True)
class Language:
    name: str = ""
    level: str = ""   # one of LANGUAGE_LEVELS, or "" (not said)


@dataclass(frozen=True)
class Reference:
    name: str = ""
    title: str = ""     # job title and company, e.g. "Manager, Daraz"
    contact: str = ""   # phone or email


@dataclass(frozen=True)
class CV:
    personal: Personal
    summary: str = ""
    experience: tuple = field(default_factory=tuple)
    education: tuple = field(default_factory=tuple)
    skills: tuple = field(default_factory=tuple)
    projects: tuple = field(default_factory=tuple)
    certifications: tuple = field(default_factory=tuple)
    languages: tuple = field(default_factory=tuple)
    hobbies: tuple = field(default_factory=tuple)
    references: tuple = field(default_factory=tuple)
    references_on_request: bool = False


@dataclass(frozen=True)
class PdfFile:
    content: bytes
    filename: str


def build_pdf(data, template, language, accent=None, photo=None):
    """Check the form data (and the optional photo, a data: URL) and turn it into a PDF.
    Raises CVError for anything the user can fix."""
    template, language, accent = check_design(template, language, accent)
    cv = parse_cv(data)
    photo_bytes = clean_photo(photo) if photo else None
    try:
        content = render_cv(template, cv, labels(language), rtl=language == "ur", language=language,
                            accent=accent, photo=photo_bytes)
    except PdfBuildError as error:
        raise CVError("pdf_failed") from error
    return PdfFile(content=content, filename=pdf_filename(cv.personal.full_name))


def clean_photo(data_url):
    """The photo as a clean JPEG, or CVError("photo_invalid" / "photo_too_large")."""
    try:
        return photos.clean_data_url(data_url)
    except photos.PhotoError as error:
        raise CVError(error.code, "photo") from None


def check_design(template, language, accent=None):
    """(template, language, accent) after checking them; a missing accent means the default."""
    if template not in TEMPLATES:
        raise CVError("template_invalid", "template")
    if language not in LANGUAGES:
        raise CVError("language_invalid", "language")
    if accent is None or accent == "":
        accent = DEFAULT_ACCENT
    if accent not in ACCENT_NAMES:
        raise CVError("accent_invalid", "accent")
    return template, language, accent


def parse_cv(data, require_name=True):
    """A clean CV from the raw JSON the form sends. Empty rows are dropped.
    `require_name=False` for saving an unfinished CV (the PDF needs a name, a draft doesn't)."""
    if not isinstance(data, dict):
        raise CVError("invalid_data")
    personal = _dict(data.get("personal"))
    full_name = _text(personal, "full_name", "personal.full_name", LIMITS["full_name"])
    if require_name and not full_name:
        raise CVError("name_required", "personal.full_name")
    email = _text(personal, "email", "personal.email", LIMITS["email"])
    if email and not _EMAIL_RE.match(email):
        raise CVError("email_invalid", "personal.email")

    return CV(
        personal=Personal(
            full_name=full_name,
            headline=_text(personal, "headline", "personal.headline", LIMITS["headline"]),
            email=email,
            phone=_text(personal, "phone", "personal.phone", LIMITS["phone"]),
            location=_text(personal, "location", "personal.location", LIMITS["location"]),
            website=_web_address(personal, "website"),
            linkedin=_web_address(personal, "linkedin"),
        ),
        summary=_text(data, "summary", "summary", LIMITS["summary"], multiline=True),
        experience=_parse_experience(data.get("experience")),
        education=_parse_entries(data.get("education"), "education", MAX_EDUCATION, Education, {
            "degree": "degree", "school": "school", "location": "location",
            "start": "date", "end": "date", "description": "description",
        }, required=("degree", "school", "description")),
        skills=_parse_words(data.get("skills"), "skills", MAX_SKILLS, LIMITS["skill"]),
        projects=_parse_entries(data.get("projects"), "projects", MAX_PROJECTS, Project, {
            "name": "project", "link": "website", "description": "description",
        }, required=("name", "description")),
        certifications=_parse_entries(data.get("certifications"), "certifications", MAX_CERTIFICATIONS,
                                      Certification, {"name": "certificate", "issuer": "issuer", "date": "date"},
                                      required=("name",)),
        languages=_parse_languages(data.get("languages")),
        hobbies=_parse_words(data.get("hobbies"), "hobbies", MAX_HOBBIES, LIMITS["hobby"]),
        references=_parse_entries(data.get("references"), "references", MAX_REFERENCES, Reference, {
            "name": "reference_name", "title": "reference_title", "contact": "reference_contact",
        }, required=("name",)),
        references_on_request=data.get("references_on_request") is True,
    )


def cv_to_dict(cv):
    """A parsed CV as plain JSON-ready data (what gets saved; the same shape the form sends)."""
    data = asdict(cv)
    for key, value in data.items():
        if isinstance(value, tuple):
            data[key] = list(value)
    return data


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
            "projects": _("Projects"),
            "certifications": _("Certifications"),
            "languages": _("Languages"),
            "hobbies": _("Hobbies"),
            "references": _("References"),
            "references_on_request": _("References available on request."),
            "levels": {
                "native": _("Native"),
                "fluent": _("Fluent"),
                "advanced": _("Advanced"),
                "intermediate": _("Intermediate"),
                "basic": _("Basic"),
            },
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
    jobs = [parse_job(item, index) for index, item in enumerate(items)]
    return tuple(job for job in jobs if job_has_content(job))


def parse_job(item, index):
    """One job from the form (its position `index` is used in error field names)."""
    item = _dict(item)
    prefix = f"experience.{index}."
    return Experience(
        job_title=_text(item, "job_title", prefix + "job_title", LIMITS["job_title"]),
        company=_text(item, "company", prefix + "company", LIMITS["company"]),
        location=_text(item, "location", prefix + "location", LIMITS["location"]),
        start=_text(item, "start", prefix + "start", LIMITS["date"]),
        end=_text(item, "end", prefix + "end", LIMITS["date"]),
        current=item.get("current") is True,
        description=_text(item, "description", prefix + "description", LIMITS["description"], multiline=True),
    )


def job_has_content(job):
    return bool(job.job_title or job.company or job.description)


def _parse_entries(raw, kind, max_items, entry_class, fields, required):
    """Rows of `kind` (e.g. "projects"). `fields`: form key -> LIMITS key. A row is kept only if
    one of the `required` fields has text."""
    items = _list(raw)
    if len(items) > max_items:
        raise CVError(f"too_many_{kind}", kind)
    entries = []
    for index, item in enumerate(items):
        item = _dict(item)
        values = {
            key: _text(item, key, f"{kind}.{index}.{key}", LIMITS[limit], multiline=key == "description")
            for key, limit in fields.items()
        }
        if "link" in values and values["link"] and not _WEBSITE_RE.match(values["link"]):
            raise CVError("website_invalid", f"{kind}.{index}.link")
        if any(values[key] for key in required):
            entries.append(entry_class(**values))
    return tuple(entries)


def _parse_languages(raw):
    items = _list(raw)
    if len(items) > MAX_LANGUAGES:
        raise CVError("too_many_languages", "languages")
    languages, seen = [], set()
    for index, item in enumerate(items):
        item = _dict(item)
        name = _text(item, "name", f"languages.{index}.name", LIMITS["language"])
        level = item.get("level") or ""
        if level not in LANGUAGE_LEVELS and level != "":
            raise CVError("invalid_data", f"languages.{index}.level")
        if name and name.casefold() not in seen:
            seen.add(name.casefold())
            languages.append(Language(name=name, level=level))
    return tuple(languages)


def _parse_words(raw, kind, max_items, max_length):
    """A list of short words (skills, hobbies): trimmed, no empties, no repeats."""
    items = _list(raw)
    if len(items) > max_items:
        raise CVError(f"too_many_{kind}", kind)
    words, seen = [], set()
    for item in items:
        if not isinstance(item, str):
            raise CVError("invalid_data", kind)
        word = _clean(item)
        if len(word) > max_length:
            raise CVError("too_long", kind)
        if word and word.casefold() not in seen:
            seen.add(word.casefold())
            words.append(word)
    return tuple(words)


def _web_address(personal, key):
    value = _text(personal, key, f"personal.{key}", LIMITS["website"])
    if value and not _WEBSITE_RE.match(value):
        raise CVError("website_invalid", f"personal.{key}")
    return value


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

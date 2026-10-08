"""The tools catalog: one entry per tool. Add a tool here and its card and page appear.

When a tool is built, change its `status` to Status.LIVE — nothing else needs to change.
"""
from dataclasses import dataclass
from enum import Enum

from flask_babel import lazy_gettext as _l


class Status(str, Enum):
    LIVE = "live"
    COMING_SOON = "coming_soon"


@dataclass(frozen=True)
class Category:
    key: str
    label: str


ALL = "all"

CATEGORIES = (
    Category(ALL, _l("All")),
    Category("cv", _l("CV")),
    Category("writing", _l("Writing")),
    Category("productivity", _l("Productivity")),
)

_CATEGORY_LABELS = {category.key: category.label for category in CATEGORIES}


@dataclass(frozen=True)
class Tool:
    slug: str
    name: str
    category: str
    icon: str          # name of an icon in templates/partials/icons.html
    summary: str       # one line, shown on the card
    status: Status = Status.COMING_SOON
    featured: bool = False  # shown inside the big "CV section" card instead of the grid

    @property
    def is_live(self):
        return self.status is Status.LIVE

    @property
    def category_label(self):
        return _CATEGORY_LABELS[self.category]


# Order matters: it is the order shown on the page (build a CV first, then check it).
TOOLS = (
    Tool(
        slug="cv-generator",
        name=_l("CV Generator"),
        category="cv",
        icon="file-plus",
        summary=_l("Fill a form, pick a template, download a polished PDF."),
        featured=True,
    ),
    Tool(
        slug="cv-checker",
        name=_l("CV Checker"),
        category="cv",
        icon="file-check",
        summary=_l("Upload your CV and get a score with clear tips from AI."),
        featured=True,
    ),
    Tool(
        slug="captions",
        name=_l("Captions"),
        category="writing",
        icon="message",
        summary=_l("Turn a topic into ready-to-post Instagram and LinkedIn captions."),
    ),
    Tool(
        slug="notes",
        name=_l("Notes"),
        category="productivity",
        icon="note",
        summary=_l("Write, edit and search your notes from any device."),
    ),
    Tool(
        slug="expenses",
        name=_l("Expenses"),
        category="productivity",
        icon="wallet",
        summary=_l("Log daily spending and see your monthly total."),
    ),
)

_TOOLS_BY_SLUG = {tool.slug: tool for tool in TOOLS}


def get_tool(slug):
    """Return the tool with this slug, or None."""
    return _TOOLS_BY_SLUG.get(slug)


def featured_tools():
    return [tool for tool in TOOLS if tool.featured]


def grid_tools():
    return [tool for tool in TOOLS if not tool.featured]

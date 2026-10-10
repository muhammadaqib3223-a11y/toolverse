"""Text content for the marketing pages. Every string is translatable."""
from dataclasses import dataclass

from flask_babel import lazy_gettext as _l


@dataclass(frozen=True)
class Step:
    number: str
    title: str
    description: str


@dataclass(frozen=True)
class FAQ:
    question: str
    answer: str


@dataclass(frozen=True)
class ComingSoonPage:
    title: str
    description: str


# Tool names shown in the dashboard preview sidebar.
PREVIEW_TOOLS = (
    _l("CV Checker"),
    _l("CV Generator"),
    _l("Captions"),
    _l("Notes"),
    _l("Expenses"),
)

STEPS = (
    Step("01", _l("Sign up free"), _l("With email or Google.")),
    Step("02", _l("Pick a tool"), _l("All five live on your dashboard.")),
    Step("03", _l("It's all saved"), _l("Come back anytime, any device.")),
)

FREE_POINTS = (
    _l("No credit card"),
    _l("No paid plans"),
    _l("All five tools included"),
)

FAQS = (
    FAQ(
        _l("Is Toolverse really free?"),
        _l("Yes. All five tools are free, with no paid plans and no credit card. "
           "AI tools have a fair daily limit so they stay free for everyone."),
    ),
    FAQ(
        _l("Why do I need to log in?"),
        _l("So your CVs, notes and expenses are saved to your own account "
           "and stay private to you, on any device."),
    ),
    FAQ(
        _l("Is my CV safe?"),
        _l("Yes. Your CV is stored privately and only you can open it. We never share it."),
    ),
    FAQ(
        _l("Can I use it in Urdu?"),
        _l("Yes. Switch to Urdu from the menu at the top and the whole site changes to Urdu."),
    ),
)

COMING_SOON_PAGES = {
    "contact": ComingSoonPage(
        _l("Contact"),
        _l("A contact page is on its way. It will be here soon."),
    ),
}

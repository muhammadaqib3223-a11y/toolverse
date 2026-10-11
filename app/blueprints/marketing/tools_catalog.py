"""The tools catalog: one entry per tool. Add a tool here and its card and page appear.

When a tool is built, change its `status` to Status.LIVE — nothing else needs to change.
Every feature written here is a promise: CLAUDE.md lists them as requirements for each tool.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from flask_babel import lazy_gettext as _l

from app.blueprints.marketing.content import FAQ
from app.blueprints.marketing.tool_articles import ARTICLES


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
class Feature:
    icon: str
    title: str
    text: str


@dataclass(frozen=True)
class HowToStep:
    title: str
    text: str


# --- The small looping demo on each tool page: input → working → result. ---

@dataclass(frozen=True)
class DemoRow:
    text: str
    hint: Optional[str] = None
    icon: Optional[str] = None
    accent: bool = False      # purple icon
    dashed: bool = False      # dashed border, like a drop zone
    progress: bool = False    # small filling progress bar on the row
    action: Optional[str] = None  # purple label on the end of the row, like a button


@dataclass(frozen=True)
class DemoStat:
    label: str
    value: str


@dataclass(frozen=True)
class Demo:
    tabs: tuple               # three step labels
    input_rows: tuple         # step 1
    working_label: str        # step 2, next to the spinner
    checks: tuple             # step 2, appear one by one
    result_rows: tuple        # step 3
    stat: Optional[DemoStat] = None  # step 3, big number box (hidden on small screens)


@dataclass(frozen=True)
class Tool:
    slug: str
    name: str
    category: str
    icon: str          # name of an icon in templates/partials/icons.html
    summary: str       # one line, shown on the card
    description: str   # shown in the tool page hero
    seo_title: str     # <title> of the tool page (" | Toolverse" is added)
    meta_description: str
    demo: Demo
    features: tuple
    steps: tuple
    faqs: tuple
    article: tuple     # long guide after Features, see tool_articles.py
    status: Status = Status.COMING_SOON
    featured: bool = False  # shown inside the big "CV section" card instead of the grid
    app_endpoint: Optional[str] = None  # url_for() endpoint of the tool itself, once status is LIVE

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
        seo_title=_l("Free CV Generator – Build a CV and Download a PDF"),
        meta_description=_l("Fill a simple form, pick a clean template and download your CV as a PDF. "
                            "Optional AI help for your summary and experience."),
        summary=_l("Fill a form, pick a template, download a polished PDF."),
        description=_l("Fill in a simple form, choose a template and download your CV as a PDF. "
                       "AI can help you write your summary and experience."),
        featured=True,
        demo=Demo(
            tabs=(_l("1 · Fill the form"), _l("2 · Pick a template"), _l("3 · Download PDF")),
            input_rows=(
                DemoRow(_l("[Your Name]"), icon="pen", accent=True),
                DemoRow(_l("[Job title] · [City]")),
                DemoRow(_l("[Experience]")),
            ),
            working_label=_l("Applying your template…"),
            checks=(_l("Adding your details"), _l("Laying out sections"), _l("Preparing your PDF")),
            result_rows=(
                DemoRow("my_cv.pdf", hint=_l("Ready to download"), icon="download", accent=True),
                DemoRow(_l("Saved to your account"), icon="check"),
            ),
        ),
        features=(
            Feature("list", _l("Simple form"), _l("Add your details step by step, no design skills needed.")),
            Feature("layout", _l("Clean templates"), _l("Pick a clean template for your CV.")),
            Feature("download", _l("PDF download"), _l("Download a ready-to-send PDF.")),
            Feature("sparkle", _l("AI writing help"), _l("Get help writing your summary and experience.")),
            Feature("save", _l("Saved and editable"), _l("Your CVs are saved, so you can edit them anytime.")),
            Feature("file-check", _l("Check it next"), _l("Check your new CV with the CV Checker.")),
        ),
        steps=(
            HowToStep(_l("Fill the form"), _l("Add your details, experience and skills.")),
            HowToStep(_l("Choose a template"), _l("Pick the design you like.")),
            HowToStep(_l("Download your PDF"), _l("Your CV is ready to send.")),
        ),
        faqs=(
            FAQ(_l('Do I need design skills?'),
                _l('No. You fill the form and the template handles the design.')),
            FAQ(_l('Can I edit my CV later?'),
                _l('Yes. Your CVs are saved in your account and you can edit them anytime.')),
            FAQ(_l('Does AI write the whole CV?'),
                _l('No. AI helps with your summary and experience, but you stay in control and can change everything.')),
            FAQ(_l('Is the CV Generator free?'),
                _l('Yes. Building and downloading your CV is free. AI writing help has a fair daily limit so it stays free for everyone.')),
            FAQ(_l('Can I download my CV without an account?'),
                _l('Yes. You can build your CV and download the PDF without logging in. To save your CV and edit it later, create a free account.')),
            FAQ(_l('What format is the download?'),
                _l('PDF. It keeps your layout the same on any device and is a common format for job applications.')),
            FAQ(_l('Can I make more than one CV?'),
                _l('Yes. Your CVs are saved in your account, so you can keep different versions, for example for different kinds of jobs.')),
            FAQ(_l('Can I check my CV after building it?'),
                _l('Yes. Use the CV Checker to get a score and tips for your new CV.')),
        ),
        article=ARTICLES['cv-generator'],
        status=Status.LIVE,
        app_endpoint="cv_generator.index",
    ),
    Tool(
        slug="cv-checker",
        name=_l("CV Checker"),
        category="cv",
        icon="file-check",
        seo_title=_l("Free AI CV Checker – Get a Score and Clear Tips"),
        meta_description=_l("Upload your CV as a PDF and get a score with clear, practical tips from AI. "
                            "Free to use and private to you."),
        summary=_l("Upload your CV and get a score with clear tips from AI."),
        description=_l("Upload your CV as a PDF. AI reads it and gives you a score and clear "
                       "suggestions to make it stronger."),
        featured=True,
        demo=Demo(
            tabs=(_l("1 · Upload"), _l("2 · AI checks"), _l("3 · Get results")),
            input_rows=(
                DemoRow(_l("Drop your CV here"), hint=_l("PDF, up to 4 MB"), icon="upload",
                        accent=True, dashed=True),
                DemoRow("my_cv.pdf", icon="file", progress=True),
            ),
            working_label=_l("AI is reading your CV…"),
            checks=(_l("Checking structure"), _l("Checking skills"), _l("Checking wording")),
            stat=DemoStat(_l("Score"), "[72]"),
            result_rows=(
                DemoRow(_l("[Tip 1 from AI]")),
                DemoRow(_l("[Tip 2 from AI]")),
                DemoRow(_l("[Tip 3 from AI]")),
            ),
        ),
        features=(
            Feature("gauge", _l("Overall score"), _l("One clear score shows where your CV stands.")),
            Feature("lightbulb", _l("Practical tips"), _l("Specific tips you can act on right away.")),
            Feature("layout", _l("Structure check"), _l("Checks that your sections are clear and in order.")),
            Feature("type", _l("Wording check"), _l("Points out weak or unclear wording.")),
            Feature("lock", _l("Private to you"), _l("Your CV is saved in your account and only you can see it.")),
            Feature("link", _l("Works with the CV Generator"), _l("Build, check and improve your CV in one place.")),
        ),
        steps=(
            HowToStep(_l("Upload your CV"), _l("Choose a PDF file up to 4 MB.")),
            HowToStep(_l("Let AI check it"), _l("It reads your CV and looks at structure, skills and wording.")),
            HowToStep(_l("Improve it"), _l("Use the score and tips to update your CV.")),
        ),
        faqs=(
            FAQ(_l('Which files can I upload?'),
                _l('PDF files up to 4 MB.')),
            FAQ(_l('Who can see my CV?'),
                _l('Only you. If you are logged in, your CV is saved privately in your account. As a guest, your file is only checked and not saved.')),
            FAQ(_l('Is the CV Checker free?'),
                _l('Yes. It is free to use. There is a fair daily limit on checks so the tool stays free for everyone.')),
            FAQ(_l('Can I check my CV without an account?'),
                _l('Yes. You can try one check without logging in. Your file is checked and not saved. Create a free account for more checks.')),
            FAQ(_l('What does the score mean?'),
                _l('It is a quick summary of how clear and complete your CV looks. It is a guide, not a decision from an employer. Use the tips to see what to improve.')),
            FAQ(_l('How long does a check take?'),
                _l('The AI needs a moment to read your CV. A progress bar shows while it works.')),
            FAQ(_l('Will it rewrite my CV?'),
                _l('No. It gives you a score and tips, and you decide what to change. To build a new CV, use the CV Generator.')),
            FAQ(_l('Is the AI always right?'),
                _l('AI gives helpful suggestions, but it can make mistakes. Use your own judgment too.')),
        ),
        article=ARTICLES['cv-checker'],
    ),
    Tool(
        slug="captions",
        name=_l("Captions"),
        category="writing",
        icon="message",
        seo_title=_l("Free Caption Generator for Instagram and LinkedIn"),
        meta_description=_l("Type a topic and get ready-to-post captions for Instagram and LinkedIn. "
                            "Copy in one tap and edit before you post."),
        summary=_l("Turn a topic into ready-to-post Instagram and LinkedIn captions."),
        description=_l("Type a topic and get ready-to-post captions for Instagram and LinkedIn. "
                       "Pick the one you like, copy it and post."),
        demo=Demo(
            tabs=(_l("1 · Type a topic"), _l("2 · AI writes"), _l("3 · Pick one")),
            input_rows=(
                DemoRow(_l("[Your topic, e.g. new job]"), icon="pen", accent=True, action=_l("Generate")),
                DemoRow(_l("Instagram · LinkedIn"), icon="message"),
            ),
            working_label=_l("Writing your captions…"),
            checks=(_l("Reading your topic"), _l("Matching the platform"), _l("Writing options")),
            result_rows=(
                DemoRow(_l("[Caption 1 from AI]"), action=_l("Copy")),
                DemoRow(_l("[Caption 2 from AI]"), action=_l("Copy")),
                DemoRow(_l("[Caption 3 from AI]"), action=_l("Copy")),
            ),
        ),
        features=(
            Feature("message", _l("Instagram and LinkedIn"), _l("Captions written for the platform you choose.")),
            Feature("layers", _l("Several options"), _l("Get more than one caption to choose from.")),
            Feature("pen", _l("Any topic"), _l("A new job, a product, an event: just type it.")),
            Feature("copy", _l("Copy in one tap"), _l("Copy a caption and paste it straight into your post.")),
            Feature("edit", _l("Edit before posting"), _l("Captions are a starting point; change any word you like.")),
            Feature("clock", _l("Fair daily limit"),
                    _l("Free to use, with a daily limit so it stays free for everyone.")),
        ),
        steps=(
            HowToStep(_l("Type a topic"), _l("Say what you want to post about.")),
            HowToStep(_l("Choose a platform"), _l("Instagram or LinkedIn.")),
            HowToStep(_l("Copy and post"), _l("Pick your favourite caption and share it.")),
        ),
        faqs=(
            FAQ(_l('Which platforms does it write for?'),
                _l('Instagram and LinkedIn.')),
            FAQ(_l('Is the Captions tool free?'),
                _l('Yes. It is free, with a fair daily limit so it stays free for everyone.')),
            FAQ(_l('Can I try it without an account?'),
                _l('Yes. You can try it up to 3 times without logging in. Create a free account to keep using it.')),
            FAQ(_l('How many captions do I get?'),
                _l('You get more than one caption for each topic, so you can pick the one you like best.')),
            FAQ(_l('Can I change a caption?'),
                _l('Yes. Captions are a starting point, so edit them before you post.')),
            FAQ(_l('Can I use the captions for my business?'),
                _l('Yes. You can use them for personal or business posts. Read and edit each caption before you post it.')),
            FAQ(_l('Does it post for me?'),
                _l('No. You copy the caption and paste it into Instagram or LinkedIn yourself. Toolverse does not connect to your social media accounts.')),
        ),
        article=ARTICLES['captions'],
        status=Status.LIVE,
        app_endpoint="captions.index",
    ),
    Tool(
        slug="notes",
        name=_l("Notes"),
        category="productivity",
        icon="note",
        seo_title=_l("Free Online Notes – Write, Edit and Search"),
        meta_description=_l("Write notes, edit them anytime and find any note with search. "
                            "Saved in your account and on every device."),
        summary=_l("Write, edit and search your notes from any device."),
        description=_l("Write notes, edit them anytime and find any note fast with search. "
                       "Your notes are saved in your account, so they are on every device you use."),
        demo=Demo(
            tabs=(_l("1 · Write"), _l("2 · Save"), _l("3 · Search")),
            input_rows=(
                DemoRow(_l("[Meeting notes]"), icon="note", accent=True),
                DemoRow(_l("[Your note text…]")),
            ),
            working_label=_l("Saving your note…"),
            checks=(_l("Saved to your account"), _l("Ready on all your devices")),
            result_rows=(
                DemoRow(_l("[meeting]"), icon="search", accent=True),
                DemoRow(_l("[Meeting notes]"), icon="note"),
            ),
        ),
        features=(
            Feature("pen", _l("Write fast"), _l("Open a new note and start typing.")),
            Feature("edit", _l("Edit anytime"), _l("Change your notes whenever you need.")),
            Feature("search", _l("Quick search"), _l("Find any note in seconds with search.")),
            Feature("trash", _l("Delete"), _l("Remove notes you no longer need.")),
            Feature("devices", _l("On every device"), _l("Log in anywhere and your notes are there.")),
            Feature("lock", _l("Private to you"), _l("Only you can see your notes.")),
        ),
        steps=(
            HowToStep(_l("Create a note"), _l("Write a title and your text.")),
            HowToStep(_l("Edit or delete it"), _l("Change it or remove it when you need to.")),
            HowToStep(_l("Search when you need it"), _l("Type a word to find a note.")),
        ),
        faqs=(
            FAQ(_l('Who can see my notes?'),
                _l('Only you.')),
            FAQ(_l('Does it work on my phone?'),
                _l('Yes. It works in the browser on phone, tablet and laptop.')),
            FAQ(_l('Do I need to install an app?'),
                _l('No. Toolverse works in your web browser.')),
            FAQ(_l('Is Notes free?'),
                _l('Yes, completely free.')),
            FAQ(_l('Can I use Notes without an account?'),
                _l('Yes. Notes you write as a guest are kept in this browser only. Create a free account to move them to your account and open them on other devices.')),
            FAQ(_l('Can I search inside my notes?'),
                _l('Yes. Type any word and Notes shows the notes that contain it.')),
            FAQ(_l('Can I get back a deleted note?'),
                _l('No. When you delete a note it is removed, so only delete notes you no longer need.')),
        ),
        article=ARTICLES['notes'],
        status=Status.LIVE,
        app_endpoint="notes.index",
    ),
    Tool(
        slug="expenses",
        name=_l("Expenses"),
        category="productivity",
        icon="wallet",
        seo_title=_l("Free Expense Tracker – Daily List and Monthly Total"),
        meta_description=_l("Log what you spend each day and see your monthly total. "
                            "Simple, private and with no bank connection."),
        summary=_l("Log daily spending and see your monthly total."),
        description=_l("Add what you spend each day and see your total for the month. "
                       "Simple tracking, saved in your account."),
        demo=Demo(
            tabs=(_l("1 · Add an expense"), _l("2 · Saved"), _l("3 · Monthly total")),
            input_rows=(
                DemoRow(_l("[Groceries]"), icon="wallet", accent=True),
                DemoRow(_l("[Amount]"), action=_l("Add")),
            ),
            working_label=_l("Adding your expense…"),
            checks=(_l("Saved to this month"), _l("Updating your total")),
            stat=DemoStat(_l("This month"), _l("[Total]")),
            result_rows=(
                DemoRow(_l("[Groceries] · [Amount]")),
                DemoRow(_l("[Transport] · [Amount]")),
                DemoRow(_l("[Bills] · [Amount]")),
            ),
        ),
        features=(
            Feature("plus", _l("Quick entry"), _l("Add an expense in a few seconds.")),
            Feature("calendar", _l("Monthly total"), _l("See how much you spent this month.")),
            Feature("list", _l("Daily list"), _l("See your expenses listed by day.")),
            Feature("lock", _l("Private to you"), _l("Only you can see your spending.")),
            Feature("devices", _l("On every device"), _l("Add expenses from your phone or laptop.")),
            Feature("shield", _l("No bank link"), _l("You add expenses yourself; no bank account is connected.")),
        ),
        steps=(
            HowToStep(_l("Add an expense"), _l("Enter the amount and what it was for.")),
            HowToStep(_l("Keep adding daily"), _l("It takes a minute a day.")),
            HowToStep(_l("Check your monthly total"), _l("See where your money went.")),
        ),
        faqs=(
            FAQ(_l('Does it connect to my bank?'),
                _l('No. You add expenses yourself, so nothing is linked to your bank.')),
            FAQ(_l('Who can see my expenses?'),
                _l('Only you.')),
            FAQ(_l('Is it free?'),
                _l('Yes, completely free.')),
            FAQ(_l('Can I use it without an account?'),
                _l('Yes. Expenses you add as a guest are kept in this browser only. Create a free account to move them to your account and see them on other devices.')),
            FAQ(_l('Can I edit or delete an expense?'),
                _l('Yes. If you make a mistake, you can change or remove an expense.')),
            FAQ(_l('How is the monthly total calculated?'),
                _l('It adds up all the expenses you entered for that month.')),
            FAQ(_l('Does it work on my phone?'),
                _l('Yes. It works in the browser on phone, tablet and laptop.')),
        ),
        article=ARTICLES['expenses'],
        status=Status.LIVE,
        app_endpoint="expenses.index",
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


def other_tools(slug):
    """Every tool except the one with this slug, for the "Other tools" section."""
    return [tool for tool in TOOLS if tool.slug != slug]

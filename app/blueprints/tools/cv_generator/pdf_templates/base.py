"""Drawing helpers shared by every CV template: columns, paragraphs, section headings, job and
education entries, bullet lists and flowing rows of items (contact details, skill chips).

Everything is mirrored for right-to-left CVs (Urdu): text is right-aligned, dates and bullets
move to the other side, and items flow from the right. Sizes are in points (A4 = 595 x 842).

ATS rules every template follows: all text is real text (no images of text), no letter-spacing
(readers split spaced letters), and sections come in reading order.
"""
import io

from app.services import pdf_builder
from app.services.pdf_builder import contains_urdu, line_height

INK = (17, 17, 19)
MUTED = (88, 88, 96)
FAINT = (140, 140, 148)
RULE = (224, 224, 229)
WHITE = (255, 255, 255)

# Accent colours the user can pick: dark enough for text on white paper, and still clear when
# printed in black and white. Names are stored with the CV; the form shows the same colours.
ACCENTS = {
    "indigo": (88, 72, 214),
    "blue": (29, 94, 196),
    "teal": (13, 118, 120),
    "green": (31, 117, 66),
    "maroon": (140, 32, 52),
    "charcoal": (45, 45, 52),
}
DEFAULT_ACCENT = "indigo"

PAGE_MARGIN = 48
BOTTOM_MARGIN = 48
SECTION_GAP = 16

BULLET_PREFIXES = ("- ", "• ", "* ", "–")
BULLET_INDENT = 12
SEPARATOR = "·"


def hex_color(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def tint(rgb, amount):
    """`rgb` mixed with white: amount 0 = unchanged, 1 = white."""
    return tuple(round(c + (255 - c) * amount) for c in rgb)


class CvLayout:
    """Base class: a template subclasses this and implements draw()."""

    extra_families = ()           # more fonts to load, e.g. (pdf_builder.SERIF,)
    body_font = pdf_builder.SANS  # main font for Latin text
    skills_style = "inline"       # "inline" (dot-separated) or "chips"

    def __init__(self, cv, labels, *, rtl=False, language="en", accent=DEFAULT_ACCENT, photo=None):
        self.cv = cv
        self.labels = labels
        self.rtl = rtl
        self.photo = photo  # clean JPEG bytes (app/services/photos.py) or None
        self.accent = ACCENTS.get(accent, ACCENTS[DEFAULT_ACCENT])
        name = cv.personal.full_name
        self.pdf = pdf_builder.new_document(
            title=f"{name} - CV", author=name, language=language, rtl=rtl, extra_families=self.extra_families
        )
        self.pdf.set_margins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        # No inner padding in cells: our own columns and gaps decide where text sits.
        self.pdf.c_margin = 0
        self.pdf.set_auto_page_break(True, margin=BOTTOM_MARGIN)
        self.pdf.add_page()
        self.full_column()

    def render(self):
        self.draw()
        return pdf_builder.render(self.pdf)

    def draw(self):
        raise NotImplementedError

    @property
    def heading_color(self):
        return INK

    # ── Columns and spacing ──────────────────────────────────────────────────

    def set_column(self, x0, x1):
        """Write between x0 and x1 from now on (page breaks keep the same column)."""
        self.col_x0, self.col_x1 = x0, x1
        self.pdf.set_left_margin(x0)
        self.pdf.set_right_margin(self.pdf.w - x1)
        self.pdf.set_x(x0)

    def full_column(self):
        self.set_column(PAGE_MARGIN, self.pdf.w - PAGE_MARGIN)

    def split(self, start_width, gutter):
        """Two columns: the first `start_width` wide on the reading-start side (left, or right
        for Urdu), the rest after a gutter. Returns ((x0, x1), (x0, x1))."""
        left, right = PAGE_MARGIN, self.pdf.w - PAGE_MARGIN
        if self.rtl:
            return (right - start_width, right), (left, right - start_width - gutter)
        return (left, left + start_width), (left + start_width + gutter, right)

    @property
    def col_w(self):
        return self.col_x1 - self.col_x0

    @property
    def align(self):
        return "R" if self.rtl else "L"

    @property
    def page_bottom(self):
        return self.pdf.h - BOTTOM_MARGIN

    def gap(self, height):
        self.pdf.set_y(self.pdf.get_y() + height)

    def ensure_space(self, height):
        """Start a new page now if less than `height` is left (keeps a heading with its text)."""
        if self.pdf.get_y() + height > self.page_bottom:
            self.pdf.add_page()

    def rule(self, color=RULE, width=0.6):
        y = self.pdf.get_y()
        self.pdf.set_draw_color(*color)
        self.pdf.set_line_width(width)
        self.pdf.line(self.col_x0, y, self.col_x1, y)

    # ── Text ─────────────────────────────────────────────────────────────────

    def font(self, size, bold=False, color=INK, text="", family=None):
        """Pick the font for `text`: Nastaliq when it has any Urdu, otherwise `family` or the
        template's body font.

        Urdu must be written with Nastaliq as the main font (not as a fallback): otherwise
        every word becomes its own piece and PDF readers (ATS, our CV Checker) read the words
        back in reverse order.
        """
        if contains_urdu(text):
            family = pdf_builder.URDU
        self.pdf.set_font(family or self.body_font, "B" if bold else "", size)
        self.pdf.set_text_color(*color)

    def text_width(self, text, size, bold=False, family=None):
        self.font(size, bold, text=text, family=family)
        return self.pdf.get_string_width(text)

    def paragraph(self, text, size, *, bold=False, color=INK, x=None, width=None, link=None,
                  align=None, family=None):
        """Wrapped text across the column (or across `width` starting at `x`)."""
        if not text:
            return
        self.font(size, bold, color, text=text, family=family)
        self.pdf.set_x(self.col_x0 if x is None else x)
        self.pdf.multi_cell(
            self.col_w if width is None else width,
            line_height(size, text),
            text,
            align=align or self.align,
            new_x="LMARGIN",
            new_y="NEXT",
            link=link or None,
        )

    def measure(self, text, size, *, bold=False, width=None, family=None):
        """Height `paragraph()` would use for this text, without drawing anything."""
        if not text:
            return 0
        self.font(size, bold, text=text, family=family)
        return self.pdf.multi_cell(
            self.col_w if width is None else width, line_height(size, text), text,
            dry_run=True, output="HEIGHT",
        )

    def heading_text(self, title):
        """Latin headings in capitals; Urdu has no capitals."""
        return title if contains_urdu(title) else title.upper()

    def section_heading(self, title, *, keep_with_next=60):
        if keep_with_next:
            self.ensure_space(keep_with_next)
        self.paragraph(self.heading_text(title), 12 if contains_urdu(title) else 10, bold=True,
                       color=self.heading_color)
        self.gap(3)
        self.rule()
        self.gap(9)

    def description(self, text, size=9.5):
        """Multi-line text; lines starting with "-", "•" or "*" become bullet points."""
        for line in text.split("\n"):
            if not line:
                self.gap(size * 0.5)
            elif line.startswith(BULLET_PREFIXES):
                self.bullet(line.lstrip("-•*– ").strip(), size)
            else:
                self.paragraph(line, size, color=MUTED)

    def bullet(self, text, size):
        if not text:
            return
        self.ensure_space(line_height(size, text))
        top = self.pdf.get_y()
        self.font(size, color=MUTED)
        bullet_x = self.col_x1 - BULLET_INDENT if self.rtl else self.col_x0
        self.pdf.set_xy(bullet_x, top)
        self.pdf.cell(BULLET_INDENT, line_height(size, text), "•", align="R" if self.rtl else "L")
        self.pdf.set_y(top)
        text_x = self.col_x0 if self.rtl else self.col_x0 + BULLET_INDENT
        self.paragraph(text, size, color=MUTED, x=text_x, width=self.col_w - BULLET_INDENT)

    # ── Sections ─────────────────────────────────────────────────────────────

    SECTION_ORDER = ("summary", "experience", "projects", "education", "certifications",
                     "skills", "languages", "hobbies", "references")

    def section_bodies(self):
        """key -> (content, draw function). Empty content = the section is left out."""
        cv = self.cv
        return {
            "summary": (cv.summary, self.summary_body),
            "experience": (cv.experience, self.experience_body),
            "projects": (cv.projects, self.projects_body),
            "education": (cv.education, self.education_body),
            "certifications": (cv.certifications, self.certifications_body),
            "skills": (cv.skills, self.skills_body),
            "languages": (cv.languages, self.languages_body),
            "hobbies": (cv.hobbies, self.hobbies_body),
            "references": (cv.references or cv.references_on_request, self.references_body),
        }

    def draw_sections(self, order=None):
        bodies = self.section_bodies()
        for key in order or self.SECTION_ORDER:
            content, body = bodies[key]
            if content:
                self.draw_section(self.labels[key], body)

    def draw_section(self, title, body):
        """A heading, then its content. Templates with a different heading layout override this."""
        self.section_heading(title)
        body()
        self.gap(SECTION_GAP)

    def summary_body(self):
        self.description(self.cv.summary, size=10)

    def experience_body(self):
        for index, job in enumerate(self.cv.experience):
            if index:
                self.gap(10)
            self.entry(job.job_title, _join(job.company, job.location),
                       self.date_range(job.start, job.end, job.current), job.description)

    def education_body(self):
        for index, item in enumerate(self.cv.education):
            if index:
                self.gap(10)
            self.entry(item.degree, _join(item.school, item.location),
                       self.date_range(item.start, item.end), item.description)

    def projects_body(self):
        for index, project in enumerate(self.cv.projects):
            if index:
                self.gap(10)
            self.entry(project.name, project.link, "", project.description)

    def certifications_body(self):
        for index, item in enumerate(self.cv.certifications):
            if index:
                self.gap(6)
            self.entry(item.name, item.issuer, item.date, "")

    def language_text(self, language):
        level = self.labels["levels"].get(language.level, "")
        return f"{language.name} ({level})" if level else language.name

    def languages_body(self):
        self.inline_items([(self.language_text(item), None) for item in self.cv.languages], 9.5, color=INK)

    def hobbies_body(self):
        self.inline_items([(hobby, None) for hobby in self.cv.hobbies], 9.5, color=INK)

    def references_body(self):
        if not self.cv.references:
            self.paragraph(self.labels["references_on_request"], 9.5, color=MUTED)
            return
        for index, ref in enumerate(self.cv.references):
            if index:
                self.gap(8)
            self.paragraph(ref.name, 10, bold=True)
            if ref.title:
                self.paragraph(ref.title, 9.5, color=MUTED)
            if ref.contact:
                self.paragraph(ref.contact, 9.5, color=MUTED)

    # ── Photo ─────────────────────────────────────────────────────────────────

    def draw_photo(self, x, y, size, ring=None):
        """The profile photo as a circle with its top-left corner at (x, y). Does nothing
        without a photo. ATS software ignores pictures, so nothing important may be only here."""
        if not self.photo:
            return
        with self.pdf.round_clip(x=x, y=y, r=size):
            self.pdf.image(io.BytesIO(self.photo), x=x, y=y, w=size, h=size)
        if ring:
            self.pdf.set_draw_color(*ring)
            self.pdf.set_line_width(2)
            self.pdf.circle(x=x + size / 2, y=y + size / 2, radius=size / 2, style="D")

    def header_beside_photo(self, size, draw_header, gap=18):
        """Run draw_header() in a column narrowed so the photo fits at the far top corner
        (right, or left for Urdu). Without a photo, draw_header() just uses the full column."""
        if not self.photo:
            draw_header()
            return
        top = self.pdf.get_y()
        x0, x1 = self.col_x0, self.col_x1
        self.draw_photo(x0 if self.rtl else x1 - size, top, size)
        self.set_column(x0 + size + gap, x1) if self.rtl else self.set_column(x0, x1 - size - gap)
        self.pdf.set_y(top)
        draw_header()
        self.set_column(x0, x1)
        self.pdf.set_y(max(self.pdf.get_y(), top + size))

    def skills_body(self):
        if self.skills_style == "chips":
            self.chips(list(self.cv.skills))
        else:
            self.inline_items([(skill, None) for skill in self.cv.skills], 9.5, color=INK)

    # ── Entries (jobs, education) ────────────────────────────────────────────

    def entry(self, title, subtitle, dates, description):
        """Bold title with dates on the far side, a muted subtitle line, then the description."""
        if not title:
            title, subtitle = subtitle, ""
        title_size, date_size = 10.5, 9
        title_lh = line_height(title_size, title)
        self.ensure_space(title_lh + 30)
        top = self.pdf.get_y()

        date_w = self.text_width(dates, date_size) + 2 if dates else 0
        spacing = 12 if dates else 0
        title_x = self.col_x0 + date_w + spacing if self.rtl else self.col_x0
        self.paragraph(title, title_size, bold=True, x=title_x, width=self.col_w - date_w - spacing)
        after_title = self.pdf.get_y()

        if dates:
            self.font(date_size, color=FAINT, text=dates)
            self.pdf.set_xy(self.col_x0 if self.rtl else self.col_x1 - date_w, top)
            self.pdf.cell(date_w, title_lh, dates, align="L" if self.rtl else "R")
            self.pdf.set_y(max(after_title, top + title_lh))

        if subtitle:
            self.paragraph(subtitle, 9.5, color=MUTED)
        if description:
            self.gap(3)
            self.description(description)

    # ── Flowing rows of items ────────────────────────────────────────────────

    def inline_layout(self, items, size):
        """Where inline_items() would put each item: (widths, rows, row_h, sep_w), or None."""
        if not items:
            return None
        self.font(size)
        sep_w = self.pdf.get_string_width(f"  {SEPARATOR}  ")
        widths = [min(self.text_width(text, size) + 1, self.col_w) for text, _link in items]
        row_h = max(line_height(size, text) for text, _link in items)
        return widths, _flow(widths, self.col_w, sep_w), row_h, sep_w

    def inline_height(self, items, size):
        layout = self.inline_layout([(text, link) for text, link in items if text], size)
        if layout is None:
            return 0
        _widths, rows, row_h, _sep_w = layout
        return (rows[-1][0] + 1) * row_h

    def inline_items(self, items, size, color=MUTED, *, centered=False, sep_color=FAINT):
        """(text, link) pairs on one line, separated by dots, wrapping when the line is full."""
        items = [(text, link) for text, link in items if text]
        layout = self.inline_layout(items, size)
        if layout is None:
            return
        widths, rows, row_h, sep_w = layout
        self.ensure_space(row_h)
        top = self.pdf.get_y()
        # For centred rows, shift every row so it sits in the middle of the column.
        shifts = {}
        if centered:
            for (row, offset), width in zip(rows, widths):
                shifts[row] = max(shifts.get(row, 0), offset + width)
            shifts = {row: (self.col_w - used) / 2 for row, used in shifts.items()}
        for (text, link), width, (row, offset) in zip(items, widths, rows):
            y = top + row * row_h
            x_offset = offset + shifts.get(row, 0)
            if offset > 0:  # not the first item on its row
                self.font(size, color=sep_color)
                self._draw_at(x_offset - sep_w, sep_w, y, row_h, SEPARATOR, None, align="C")
            self.font(size, color=color, text=text)
            self._draw_at(x_offset, width, y, row_h, text, link)
        self.pdf.set_y(top + (rows[-1][0] + 1) * row_h)

    def chips(self, items, size=8.5, border=RULE, text_color=INK):
        """Skills as small rounded tags that wrap onto new lines."""
        geometry = self.chips_geometry(items, size)
        if geometry is None:
            return
        widths, rows, chip_h, gap = geometry
        self.ensure_space(chip_h)
        top = self.pdf.get_y()
        self.pdf.set_draw_color(*border)
        self.pdf.set_line_width(0.6)
        for text, width, (row, offset) in zip(items, widths, rows):
            y = top + row * (chip_h + gap)
            x = self.col_x1 - offset - width if self.rtl else self.col_x0 + offset
            self.pdf.rect(x, y, width, chip_h, style="D", round_corners=True, corner_radius=chip_h / 2)
            self.pdf.set_xy(x, y)
            self.font(size, color=text_color, text=text)
            self.pdf.cell(width, chip_h, text, align="C")
        self.pdf.set_y(top + (rows[-1][0] + 1) * (chip_h + gap) - gap)

    def chips_height(self, items, size=8.5):
        geometry = self.chips_geometry(items, size)
        if geometry is None:
            return 0
        _widths, rows, chip_h, gap = geometry
        return (rows[-1][0] + 1) * (chip_h + gap) - gap

    def chips_geometry(self, items, size):
        if not items:
            return None
        padding, gap = 8, 5
        widths = [min(self.text_width(text, size) + 2 * padding, self.col_w) for text in items]
        chip_h = max(line_height(size, text) for text in items) + 3
        return widths, _flow(widths, self.col_w, gap), chip_h, gap

    def _draw_at(self, offset, width, y, height, text, link, align=None):
        x = self.col_x1 - offset - width if self.rtl else self.col_x0 + offset
        self.pdf.set_xy(x, y)
        self.pdf.cell(width, height, text, align=align or self.align, link=link or "")

    # ── Data helpers ─────────────────────────────────────────────────────────

    def contact_items(self):
        personal = self.cv.personal
        items = [
            (personal.email, f"mailto:{personal.email}" if personal.email else None),
            (personal.phone, None),
            (personal.location, None),
            (personal.linkedin, personal.linkedin_url or None),
            (personal.website, personal.website_url or None),
        ]
        return [(text, link) for text, link in items if text]

    def date_range(self, start, end, current=False):
        end = self.labels["present"] if current else end
        if start and end:
            return f"{start} – {end}"
        return start or end


def _join(*parts):
    return f"  {SEPARATOR}  ".join(part for part in parts if part)


def _flow(widths, max_width, gap):
    """Place boxes of `widths` left to right, wrapping at `max_width`: [(row, offset), ...]."""
    positions = []
    row, cursor = 0, 0.0
    for width in widths:
        if cursor > 0 and cursor + gap + width > max_width:
            row, cursor = row + 1, 0.0
        offset = cursor + gap if cursor > 0 else 0.0
        positions.append((row, offset))
        cursor = offset + width
    return positions

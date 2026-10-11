"""Drawing helpers shared by every CV template: columns, paragraphs, section headings, job and
education entries, bullet lists and flowing rows of items (contact details, skill chips).

Everything is mirrored for right-to-left CVs (Urdu): text is right-aligned, dates and bullets
move to the left/right side, and items flow from the right. Sizes are in points (A4 = 595 x 842).
"""
from app.services import pdf_builder
from app.services.pdf_builder import contains_urdu, line_height

INK = (17, 17, 19)
MUTED = (88, 88, 96)
FAINT = (140, 140, 148)
RULE = (224, 224, 229)
# The site's purple (#9B8CFF) is too light for text on white paper; this is a darker shade of it.
ACCENT = (98, 80, 220)

PAGE_MARGIN = 48
BOTTOM_MARGIN = 48

BULLET_PREFIXES = ("- ", "• ", "* ", "–")
BULLET_INDENT = 12
SEPARATOR = "·"


class CvLayout:
    """Base class: a template subclasses this and implements draw()."""

    heading_color = INK

    def __init__(self, cv, labels, *, rtl=False, language="en"):
        self.cv = cv
        self.labels = labels
        self.rtl = rtl
        name = cv.personal.full_name
        self.pdf = pdf_builder.new_document(title=f"{name} - CV", author=name, language=language, rtl=rtl)
        self.pdf.set_margins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        # No inner padding in cells: our own columns and gaps decide where text sits.
        self.pdf.c_margin = 0
        self.pdf.set_auto_page_break(True, margin=BOTTOM_MARGIN)
        self.pdf.add_page()
        self.set_column(PAGE_MARGIN, self.pdf.w - PAGE_MARGIN)

    def render(self):
        self.draw()
        return pdf_builder.render(self.pdf)

    def draw(self):
        raise NotImplementedError

    # ── Columns and spacing ──────────────────────────────────────────────────

    def set_column(self, x0, x1):
        """Write between x0 and x1 from now on (page breaks keep the same column)."""
        self.col_x0, self.col_x1 = x0, x1
        self.pdf.set_left_margin(x0)
        self.pdf.set_right_margin(self.pdf.w - x1)
        self.pdf.set_x(x0)

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

    def font(self, size, bold=False, color=INK, text=""):
        """Pick the font for `text`: Nastaliq when it has any Urdu, Geist otherwise.

        Urdu must be written with Nastaliq as the main font (not as Geist's fallback): otherwise
        every word becomes its own piece and PDF readers (ATS, our CV Checker) read the words
        back in reverse order.
        """
        family = pdf_builder.URDU if contains_urdu(text) else pdf_builder.SANS
        self.pdf.set_font(family, "B" if bold else "", size)
        self.pdf.set_text_color(*color)

    def text_width(self, text, size, bold=False):
        self.font(size, bold, text=text)
        return self.pdf.get_string_width(text)

    def paragraph(self, text, size, *, bold=False, color=INK, x=None, width=None, link=None):
        """Wrapped text across the column (or across `width` starting at `x`)."""
        if not text:
            return
        self.font(size, bold, color, text=text)
        self.pdf.set_x(self.col_x0 if x is None else x)
        self.pdf.multi_cell(
            self.col_w if width is None else width,
            line_height(size, text),
            text,
            align=self.align,
            new_x="LMARGIN",
            new_y="NEXT",
            link=link or None,
        )

    def section_heading(self, title, *, keep_with_next=60, color=None):
        if keep_with_next:
            self.ensure_space(keep_with_next)
        # No letter-spacing: PDF readers would read spaced letters as "E X P E R I E N C E".
        latin = not contains_urdu(title)
        self.paragraph(title.upper() if latin else title, 10 if latin else 12, bold=True,
                       color=color or self.heading_color)
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
        self.pdf.cell(BULLET_INDENT, line_height(size, text), "•", align="L" if not self.rtl else "R")
        self.pdf.set_y(top)
        text_x = self.col_x0 if self.rtl else self.col_x0 + BULLET_INDENT
        self.paragraph(text, size, color=MUTED, x=text_x, width=self.col_w - BULLET_INDENT)

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

    def inline_items(self, items, size, color=MUTED):
        """(text, link) pairs on one line, separated by dots, wrapping when the line is full."""
        items = [(text, link) for text, link in items if text]
        if not items:
            return
        self.font(size, color=color)
        sep_w = self.pdf.get_string_width(f"  {SEPARATOR}  ")
        widths = [self.text_width(text, size) + 1 for text, _link in items]
        row_h = max(line_height(size, text) for text, _link in items)
        self.ensure_space(row_h)
        rows = _flow(widths, self.col_w, sep_w)
        top = self.pdf.get_y()
        for (text, link), width, (row, offset) in zip(items, widths, rows):
            y = top + row * row_h
            if offset > 0:
                self.font(size, color=FAINT)
                self._draw_at(offset - sep_w, sep_w, y, row_h, SEPARATOR, None, align="C")
            self.font(size, color=color, text=text)
            self._draw_at(offset, min(width, self.col_w), y, row_h, text, link)
        self.pdf.set_y(top + (rows[-1][0] + 1) * row_h)

    def chips(self, items, size=8.5):
        """Skills as small rounded tags that wrap onto new lines."""
        geometry = self.chips_geometry(items, size)
        if geometry is None:
            return
        widths, rows, chip_h, gap = geometry
        self.ensure_space(chip_h)
        top = self.pdf.get_y()
        self.pdf.set_draw_color(*RULE)
        self.pdf.set_line_width(0.6)
        for text, width, (row, offset) in zip(items, widths, rows):
            y = top + row * (chip_h + gap)
            x = self.col_x1 - offset - width if self.rtl else self.col_x0 + offset
            self.pdf.rect(x, y, width, chip_h, style="D", round_corners=True, corner_radius=chip_h / 2)
            self.pdf.set_xy(x, y)
            self.font(size, color=INK, text=text)
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
        return [
            (personal.email, f"mailto:{personal.email}" if personal.email else None),
            (personal.phone, None),
            (personal.location, None),
            (personal.website, personal.website_url or None),
        ]

    def date_range(self, start, end, current=False):
        end = self.labels["present"] if current else end
        if start and end:
            return f"{start} – {end}"
        return start or end

    def draw_experience(self):
        if not self.cv.experience:
            return
        self.section_heading(self.labels["experience"])
        for index, job in enumerate(self.cv.experience):
            if index:
                self.gap(10)
            self.entry(
                job.job_title,
                _join(job.company, job.location),
                self.date_range(job.start, job.end, job.current),
                job.description,
            )
        self.gap(16)

    def draw_education(self):
        if not self.cv.education:
            return
        self.section_heading(self.labels["education"])
        for index, item in enumerate(self.cv.education):
            if index:
                self.gap(10)
            self.entry(item.degree, _join(item.school, item.location),
                       self.date_range(item.start, item.end), item.description)
        self.gap(16)

    def draw_summary(self):
        if not self.cv.summary:
            return
        self.section_heading(self.labels["summary"])
        self.description(self.cv.summary, size=10)
        self.gap(16)


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

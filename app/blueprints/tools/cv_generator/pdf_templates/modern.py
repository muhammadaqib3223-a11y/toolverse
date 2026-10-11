"""Modern: name on top, then a narrow side column (photo, contact, skills, languages, hobbies)
next to the main column (summary, experience, projects, education, ...). Accent-coloured
headings. The side column moves right for Urdu CVs.
"""
from app.blueprints.tools.cv_generator.pdf_templates.base import INK, RULE, CvLayout

SIDE_WIDTH = 150
GUTTER = 28
PHOTO_SIZE = 96


class ModernLayout(CvLayout):
    skills_style = "chips"
    SIDE_SECTIONS = ("skills", "languages", "hobbies")

    @property
    def heading_color(self):
        return self.accent

    def draw(self):
        personal = self.cv.personal
        self.paragraph(personal.full_name, 26, bold=True)
        if personal.headline:
            self.gap(3)
            self.paragraph(personal.headline, 12.5, color=self.accent)
        self.gap(20)

        side, main = self.split(SIDE_WIDTH, GUTTER)
        columns_top = self.pdf.get_y()

        # The side column must fit on the first page (going back to page 1 afterwards would
        # break the main column's page flow). Sections that don't fit go in the main column.
        self.set_column(*side)
        in_side = self._draw_side_column(columns_top)
        side_bottom = self.pdf.get_y()

        divider_x = side[0] - GUTTER / 2 if self.rtl else side[1] + GUTTER / 2
        self.pdf.set_draw_color(*RULE)
        self.pdf.set_line_width(0.6)
        self.pdf.line(divider_x, columns_top, divider_x, side_bottom)

        self.set_column(*main)
        self.pdf.set_y(columns_top)
        self.draw_sections([key for key in self.SECTION_ORDER if key not in in_side])

    def _draw_side_column(self, top):
        """Draws what fits; returns the section keys drawn here."""
        self.pdf.set_y(top)
        if self.photo:
            x = self.col_x1 - PHOTO_SIZE if self.rtl else self.col_x0
            self.draw_photo(x, top, PHOTO_SIZE, ring=self.accent)
            self.pdf.set_y(top + PHOTO_SIZE + 16)

        contacts = self.contact_items()
        if contacts:
            self.section_heading(self.labels["contact"], keep_with_next=0)
            for text, link in contacts:
                self.paragraph(text, 9, color=INK, link=link)
                self.gap(3)
            self.gap(14)

        drawn = []
        bodies = self.section_bodies()
        for key in self.SIDE_SECTIONS:
            content, _body = bodies[key]
            if not content:
                continue
            if self.pdf.get_y() + 40 + self._side_height(key) > self.page_bottom:
                continue
            self.section_heading(self.labels[key], keep_with_next=0)
            self._side_body(key)
            self.gap(14)
            drawn.append(key)
        return drawn

    def _side_height(self, key):
        if key == "skills":
            return self.chips_height(list(self.cv.skills))
        items = [self.language_text(item) for item in self.cv.languages] if key == "languages" else list(self.cv.hobbies)
        return sum(self.measure(text, 9) + 3 for text in items)

    def _side_body(self, key):
        if key == "skills":
            self.chips(list(self.cv.skills))
            return
        items = [self.language_text(item) for item in self.cv.languages] if key == "languages" else list(self.cv.hobbies)
        for text in items:
            self.paragraph(text, 9, color=INK)
            self.gap(3)

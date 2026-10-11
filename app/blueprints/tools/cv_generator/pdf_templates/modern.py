"""Modern: name on top, then a narrow side column (contact, skills) next to the main column
(summary, experience, education). Accent-coloured headings. The side column moves right for
Urdu CVs.
"""
from app.blueprints.tools.cv_generator.pdf_templates.base import INK, RULE, CvLayout

SIDE_WIDTH = 150
GUTTER = 28


class ModernLayout(CvLayout):
    skills_style = "chips"

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
        # break the main column's page flow). If the skills are too many, they go in the main column.
        self.set_column(*side)
        skills_in_side = self._draw_side_column(columns_top)
        side_bottom = self.pdf.get_y()

        divider_x = side[0] - GUTTER / 2 if self.rtl else side[1] + GUTTER / 2
        self.pdf.set_draw_color(*RULE)
        self.pdf.set_line_width(0.6)
        self.pdf.line(divider_x, columns_top, divider_x, side_bottom)

        self.set_column(*main)
        self.pdf.set_y(columns_top)
        order = ("summary", "experience", "education") if skills_in_side else (
            "summary", "experience", "education", "skills")
        self.draw_sections(order)

    def _draw_side_column(self, top):
        self.pdf.set_y(top)
        contacts = self.contact_items()
        if contacts:
            self.section_heading(self.labels["contact"], keep_with_next=0)
            for text, link in contacts:
                self.paragraph(text, 9, color=INK, link=link)
                self.gap(3)
            self.gap(14)

        if not self.cv.skills:
            return True
        skills = list(self.cv.skills)
        heading_room = 40
        if self.pdf.get_y() + heading_room + self.chips_height(skills) > self.page_bottom:
            return False
        self.section_heading(self.labels["skills"], keep_with_next=0)
        self.chips(skills)
        return True

"""Minimal: lots of white space. Each section's name sits in a narrow label column beside its
content, with a hairline between sections. One reading order, so it stays ATS-safe."""
from app.blueprints.tools.cv_generator.pdf_templates.base import MUTED, RULE, SECTION_GAP, CvLayout
from app.services.pdf_builder import contains_urdu

LABEL_WIDTH = 105
GUTTER = 22


class MinimalLayout(CvLayout):
    def draw(self):
        personal = self.cv.personal
        self.paragraph(personal.full_name, 22, bold=True)
        if personal.headline:
            self.gap(2)
            self.paragraph(personal.headline, 11.5, color=self.accent)
        if self.contact_items():
            self.gap(8)
            self.inline_items(self.contact_items(), 9, color=MUTED)
        self.gap(26)
        self._first_section = True
        self.draw_sections()

    def draw_section(self, title, body):
        self.full_column()
        self.ensure_space(70)
        if not self._first_section:
            self.rule(color=RULE, width=0.5)
            self.gap(14)
        self._first_section = False

        label, content = self.split(LABEL_WIDTH, GUTTER)
        top = self.pdf.get_y()
        self.set_column(*label)
        self.paragraph(self.heading_text(title), 11 if contains_urdu(title) else 8.5, bold=True,
                       color=self.accent)
        label_bottom, label_page = self.pdf.get_y(), self.pdf.page

        self.set_column(*content)
        self.pdf.set_y(top)
        body()
        if self.pdf.page == label_page:
            self.pdf.set_y(max(self.pdf.get_y(), label_bottom))
        self.full_column()
        self.gap(SECTION_GAP)

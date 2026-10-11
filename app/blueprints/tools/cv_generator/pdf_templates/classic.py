"""Classic: one column, black and grey with one accent line under the header.
Safe for any job and any ATS."""
from app.blueprints.tools.cv_generator.pdf_templates.base import MUTED, CvLayout


class ClassicLayout(CvLayout):
    def draw(self):
        personal = self.cv.personal
        self.paragraph(personal.full_name, 24, bold=True)
        if personal.headline:
            self.gap(2)
            self.paragraph(personal.headline, 12, color=MUTED)
        if self.contact_items():
            self.gap(8)
            self.inline_items(self.contact_items(), 9)
        self.gap(14)
        self.rule(color=self.accent, width=1.2)
        self.gap(18)
        self.draw_sections()

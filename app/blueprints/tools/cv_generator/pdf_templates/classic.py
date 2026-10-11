"""Classic: one column, black and grey only. Safe for any job and any ATS."""
from app.blueprints.tools.cv_generator.pdf_templates.base import INK, MUTED, CvLayout


class ClassicLayout(CvLayout):
    heading_color = INK

    def draw(self):
        personal = self.cv.personal
        self.paragraph(personal.full_name, 24, bold=True)
        if personal.headline:
            self.gap(2)
            self.paragraph(personal.headline, 12, color=MUTED)
        if any(text for text, _link in self.contact_items()):
            self.gap(8)
            self.inline_items(self.contact_items(), 9)
        self.gap(14)
        self.rule(color=INK, width=0.8)
        self.gap(18)

        self.draw_summary()
        self.draw_experience()
        self.draw_education()
        if self.cv.skills:
            self.section_heading(self.labels["skills"])
            self.inline_items([(skill, None) for skill in self.cv.skills], 9.5, color=INK)

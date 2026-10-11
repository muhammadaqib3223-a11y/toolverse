"""Executive: formal and centred. Source Serif throughout (a print font, not the website's),
a double accent line under the header, and serif capitals for headings. One column, ATS-safe."""
from app.blueprints.tools.cv_generator.pdf_templates.base import MUTED, RULE, CvLayout
from app.services import pdf_builder
from app.services.pdf_builder import contains_urdu


class ExecutiveLayout(CvLayout):
    extra_families = (pdf_builder.SERIF,)
    body_font = pdf_builder.SERIF

    @property
    def heading_color(self):
        return self.accent

    def draw(self):
        personal = self.cv.personal
        if self.photo:
            size = 84
            top = self.pdf.get_y()
            self.draw_photo((self.pdf.w - size) / 2, top, size, ring=self.accent)
            self.pdf.set_y(top + size + 12)
        self.paragraph(personal.full_name, 25, bold=True, align="C")
        if personal.headline:
            self.gap(3)
            self.paragraph(personal.headline, 12, color=MUTED, align="C")
        if self.contact_items():
            self.gap(9)
            self.inline_items(self.contact_items(), 9.5, centered=True)
        self.gap(14)
        self.rule(color=self.accent, width=1.4)
        self.gap(2.5)
        self.rule(color=self.accent, width=0.5)
        self.gap(20)
        self.draw_sections()

    def section_heading(self, title, *, keep_with_next=60):
        self.ensure_space(keep_with_next)
        urdu = contains_urdu(title)
        self.paragraph(self.heading_text(title), 12.5 if urdu else 11, bold=True, color=self.accent)
        self.gap(3)
        self.rule(color=RULE, width=0.6)
        self.gap(9)

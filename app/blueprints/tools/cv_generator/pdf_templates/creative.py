"""Creative: a full-width accent band with the name and contact details, short accent bars
under the headings, and skills as tags. Still one column, so ATS software reads it in order."""
from app.blueprints.tools.cv_generator.pdf_templates.base import WHITE, CvLayout, tint
from app.services.pdf_builder import contains_urdu

BAND_TOP = 40
BAND_BOTTOM_PADDING = 26
BAR_WIDTH = 28
BAR_HEIGHT = 2.5


class CreativeLayout(CvLayout):
    skills_style = "chips"

    @property
    def heading_color(self):
        return self.accent

    def draw(self):
        personal = self.cv.personal
        contacts = self.contact_items()
        name_h = self.measure(personal.full_name, 26, bold=True)
        headline_h = self.measure(personal.headline, 12.5) + 3 if personal.headline else 0
        contacts_h = self.inline_height(contacts, 9) + 10 if contacts else 0
        band_h = BAND_TOP + name_h + headline_h + contacts_h + BAND_BOTTOM_PADDING

        self.pdf.set_fill_color(*self.accent)
        self.pdf.rect(0, 0, self.pdf.w, band_h, style="F")

        self.pdf.set_y(BAND_TOP)
        self.paragraph(personal.full_name, 26, bold=True, color=WHITE)
        if personal.headline:
            self.gap(3)
            self.paragraph(personal.headline, 12.5, color=tint(self.accent, 0.82))
        if contacts:
            self.gap(10)
            light = tint(self.accent, 0.75)
            self.inline_items(contacts, 9, color=WHITE, sep_color=light)

        self.pdf.set_y(band_h + 26)
        self.draw_sections()

    def section_heading(self, title, *, keep_with_next=60):
        self.ensure_space(keep_with_next)
        urdu = contains_urdu(title)
        self.paragraph(self.heading_text(title), 12.5 if urdu else 10.5, bold=True, color=self.accent)
        self.gap(2)
        bar_x = self.col_x1 - BAR_WIDTH if self.rtl else self.col_x0
        self.pdf.set_fill_color(*self.accent)
        self.pdf.rect(bar_x, self.pdf.get_y(), BAR_WIDTH, BAR_HEIGHT, style="F")
        self.gap(BAR_HEIGHT + 10)

    def skills_body(self):
        self.chips(list(self.cv.skills), border=tint(self.accent, 0.55))

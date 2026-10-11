"""The CV designs. Each one is a CvLayout subclass (base.py). To add a design: write its file,
add it to LAYOUTS here, and add its thumbnail to the form's template picker."""
from app.blueprints.tools.cv_generator.pdf_templates.base import ACCENTS, DEFAULT_ACCENT, hex_color
from app.blueprints.tools.cv_generator.pdf_templates.classic import ClassicLayout
from app.blueprints.tools.cv_generator.pdf_templates.creative import CreativeLayout
from app.blueprints.tools.cv_generator.pdf_templates.executive import ExecutiveLayout
from app.blueprints.tools.cv_generator.pdf_templates.minimal import MinimalLayout
from app.blueprints.tools.cv_generator.pdf_templates.modern import ModernLayout

# Order = order in the template picker. The first one is the default.
LAYOUTS = {
    "modern": ModernLayout,
    "classic": ClassicLayout,
    "minimal": MinimalLayout,
    "creative": CreativeLayout,
    "executive": ExecutiveLayout,
}

# One column, plain reading order: the safest choices for older ATS software.
ATS_SAFEST = ("classic", "minimal", "executive")

ACCENT_HEX = {name: hex_color(rgb) for name, rgb in ACCENTS.items()}


def render_cv(template, cv, labels, *, rtl=False, language="en", accent=DEFAULT_ACCENT, photo=None):
    """The CV as PDF bytes. `photo`: clean JPEG bytes or None.
    Raises pdf_builder.PdfBuildError if the PDF can't be made."""
    return LAYOUTS[template](cv, labels, rtl=rtl, language=language, accent=accent, photo=photo).render()

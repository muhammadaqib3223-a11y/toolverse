"""The CV designs. Each one is a CvLayout subclass (base.py); add a new design here and to
services.TEMPLATES (and the form's template picker)."""
from app.blueprints.tools.cv_generator.pdf_templates.classic import ClassicLayout
from app.blueprints.tools.cv_generator.pdf_templates.modern import ModernLayout

LAYOUTS = {
    "classic": ClassicLayout,
    "modern": ModernLayout,
}


def render_cv(template, cv, labels, *, rtl=False, language="en"):
    """The CV as PDF bytes. Raises pdf_builder.PdfBuildError if the PDF can't be made."""
    return LAYOUTS[template](cv, labels, rtl=rtl, language=language).render()

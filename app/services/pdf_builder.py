"""Makes PDF files with fpdf2 (pure Python, so it runs on Vercel without system packages).

Every document gets the same setup: Geist for Latin text, Noto Nastaliq Urdu as a fallback
font for Urdu, and HarfBuzz text shaping (uharfbuzz) so Urdu letters join and run right to
left. Text is real text, not pictures, so it can be selected, copied and read by ATS software
and by our CV Checker.

The font files live in app/assets/fonts/ (inside the app package, so Vercel ships them with
the function just like the templates and translations).
"""
import logging
import re
from pathlib import Path

from fpdf import FPDF

log = logging.getLogger(__name__)
# fontTools (used by fpdf2 to shrink the fonts) logs every step at INFO; keep only real problems.
logging.getLogger("fontTools").setLevel(logging.WARNING)

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
SANS = "geist"
URDU = "nastaliq"

# Plain (non-variable) Regular and Bold files: fpdf2 loads these fast. Building a weight out of
# a variable font on every request took seconds.
FONT_FILES = {
    SANS: {"": "Geist-Regular.ttf", "B": "Geist-Bold.ttf"},
    URDU: {"": "NotoNastaliqUrdu-Regular.ttf", "B": "NotoNastaliqUrdu-Bold.ttf"},
}

# Arabic-script letters (Urdu uses these blocks). Used to pick line height and alignment.
_URDU_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
_URDU_RE = re.compile("[" + "".join(f"{chr(low)}-{chr(high)}" for low, high in _URDU_RANGES) + "]")

# Nastaliq letters climb and drop far more than Latin ones, so Urdu lines need more room.
LATIN_LINE_HEIGHT = 1.4
URDU_LINE_HEIGHT = 2.1

# Shaped Urdu uses extra glyphs (dots, joins) that carry no letter of their own. fpdf2 leaves
# them out of the PDF's text map, so text extraction turns them into random symbols. We map
# them to a zero-width space instead: invisible, and easy for a reader to drop.
INVISIBLE_GLYPH_TEXT = chr(0x200B)


class PdfBuildError(Exception):
    """The PDF could not be made (missing font file, fpdf2 failure)."""


def contains_urdu(text):
    return bool(text) and _URDU_RE.search(text) is not None


def line_height(font_size, text=""):
    """Line height in points for `text` at `font_size`."""
    return font_size * (URDU_LINE_HEIGHT if contains_urdu(text) else LATIN_LINE_HEIGHT)


def new_document(*, title="", author="", language="en", rtl=False):
    """An empty A4 document (units: points) with our fonts and Urdu shaping ready."""
    try:
        pdf = FPDF(unit="pt", format="A4")
        for family, styles in FONT_FILES.items():
            for style, file_name in styles.items():
                pdf.add_font(family, style, FONTS_DIR / file_name)
    except (OSError, ValueError) as error:
        log.exception("PDF fonts could not be loaded from %s", FONTS_DIR)
        raise PdfBuildError("fonts_missing") from error

    # A letter the current font doesn't have is taken from the other font. Templates still pick
    # Nastaliq as the main font for Urdu text (see cv_generator/pdf_templates/base.py).
    pdf.set_fallback_fonts([URDU, SANS], exact_match=False)
    # No fixed direction: each paragraph follows its first letter, like dir="auto" in HTML.
    pdf.set_text_shaping(True)
    pdf.set_creator("Toolverse")
    pdf.set_producer("Toolverse")
    pdf.set_lang("ur" if rtl or language == "ur" else "en")
    if title:
        pdf.set_title(title)
    if author:
        pdf.set_author(author)
    return pdf


def render(pdf):
    """The finished PDF as bytes."""
    _map_invisible_glyphs(pdf)
    try:
        return bytes(pdf.output())
    except Exception as error:  # fpdf2 raises many error types; the user only needs "failed"
        log.exception("PDF output failed")
        raise PdfBuildError("output_failed") from error


def _map_invisible_glyphs(pdf):
    for font in pdf.fonts.values():
        subset = getattr(font, "subset", None)
        if subset is None:  # built-in fonts have no subset (we don't use them, but be safe)
            continue
        for glyph, _code in subset.items():
            if glyph is not None and isinstance(glyph.unicode, tuple) and not glyph.unicode:
                glyph.unicode = (ord(INVISIBLE_GLYPH_TEXT),)

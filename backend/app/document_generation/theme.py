"""Color themes for generated presentations: validation, keyword palettes, template extraction.

Only two colors vary (the rest of the brand is fixed): `primary` (titles, key words, numbers) and `tint`
(title bars and cover panel). Code, not the model, guarantees they stay readable.
"""

import colorsys
import io
import re
import unicodedata
from collections import Counter

from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.document_generation.brand import HEX, Brand

MIN_PRIMARY_CONTRAST = 4.5  # WCAG AA for normal text, on white and on the tint bar
MAX_PAGES_SCANNED = 40


class Theme(BaseModel):
    primary: str = Field(pattern=HEX)
    tint: str = Field(pattern=HEX)


def _norm(h: str) -> str:
    return h.strip().lstrip("#").upper()


def _rgb(h: str) -> tuple[float, float, float]:
    h = _norm(h)
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def _hex(r: float, g: float, b: float) -> str:
    return "".join(f"{round(max(0.0, min(1.0, c)) * 255):02X}" for c in (r, g, b))


def luminance(h: str) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def hls(h: str) -> tuple[float, float, float]:
    return colorsys.rgb_to_hls(*_rgb(h))


def make_theme(primary: str, tint: str) -> Theme | None:
    """Normalise two hex colors into a readable theme, or None if they are not valid hex."""
    if not (re.fullmatch(HEX, _norm(primary)) and re.fullmatch(HEX, _norm(tint))):
        return None
    hue_p, light_p, sat_p = hls(primary)
    hue_t, light_t, sat_t = hls(tint)
    if light_t < 0.88:  # too dark for a background behind red-ish text: lighten, keep the hue
        tint = _hex(*colorsys.hls_to_rgb(hue_t, 0.93, min(sat_t, 0.9)))
    p = _norm(primary)
    while (
        contrast(p, "FFFFFF") < MIN_PRIMARY_CONTRAST
        or contrast(p, tint) < MIN_PRIMARY_CONTRAST - 0.5
    ) and light_p > 0.05:
        light_p -= 0.02
        p = _hex(*colorsys.hls_to_rgb(hue_p, light_p, sat_p))
    return Theme(primary=p, tint=_norm(tint))


def themed_brand(brand: Brand, theme: Theme | None) -> Brand:
    if theme is None:
        return brand
    colors = brand.colors.model_copy(
        update={"red": theme.primary, "peach": theme.tint, "cover_panel": theme.tint}
    )
    return brand.model_copy(update={"colors": colors})


def brand_theme(brand: Brand) -> Theme:
    return Theme(primary=_norm(brand.colors.red), tint=_norm(brand.colors.peach))


# ---- keyword palettes (deterministic fallback when the model gives no usable colors) ----------
_PALETTES: dict[str, tuple[str, str]] = {
    "vert": ("2E7D32", "E4F2E5"),
    "green": ("2E7D32", "E4F2E5"),
    "nature": ("2E7D32", "E4F2E5"),
    "foret": ("2F6B3A", "E3F0E4"),
    "outdoor": ("2F6B3A", "E3F0E4"),
    "bleu": ("1F5F99", "E1EDF7"),
    "blue": ("1F5F99", "E1EDF7"),
    "ocean": ("0F6B8A", "DDF0F6"),
    "mer": ("0F6B8A", "DDF0F6"),
    "ciel": ("2A6FB0", "E3EFFA"),
    "rouge": ("B00020", "FBE3E6"),
    "red": ("B00020", "FBE3E6"),
    "rose": ("B0306A", "FBE4EE"),
    "pink": ("B0306A", "FBE4EE"),
    "violet": ("6A3FA0", "EEE6F7"),
    "purple": ("6A3FA0", "EEE6F7"),
    "orange": ("B85A00", "FDEBD9"),
    "jaune": ("8A6D00", "FCF3CF"),
    "yellow": ("8A6D00", "FCF3CF"),
    "terre": ("8A4B2A", "F3E6DC"),
    "marron": ("7A4A2B", "F2E7DD"),
    "noir": ("222222", "EDEDED"),
    "gris": ("444B54", "ECEEF0"),
    "sobre": ("444B54", "ECEEF0"),
}


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]+", " ", text)


def palette_from_keywords(text: str) -> Theme | None:
    """'vert, bleu, nature' -> green primary on a light-blue tint (first word leads, second tints)."""
    found: list[tuple[str, str]] = []
    for word in _plain(text).split():
        pal = _PALETTES.get(word) or _PALETTES.get(word.rstrip("s"))
        if pal and pal not in found:
            found.append(pal)
    if not found:
        return None
    primary = found[0][0]
    tint = (found[1] if len(found) > 1 else found[0])[1]
    return make_theme(primary, tint)


# ---- template PDF: palette and text -------------------------------------------------------
_COLOR_OP = re.compile(rb"(-?\d*\.?\d+)\s+(-?\d*\.?\d+)\s+(-?\d*\.?\d+)\s+(?:rg|RG)\b")


def extract_template_palette(pdf: bytes) -> Theme | None:
    """Most used strong color -> primary, most used light non-white color -> tint (pypdf only)."""
    counts: Counter[str] = Counter()
    try:
        reader = PdfReader(io.BytesIO(pdf))
        for page in reader.pages[:MAX_PAGES_SCANNED]:
            contents = page.get_contents()
            if contents is None:
                continue
            for m in _COLOR_OP.finditer(contents.get_data()):
                r, g, b = (float(x) for x in m.groups())
                if all(0 <= c <= 1 for c in (r, g, b)):
                    counts[_hex(r, g, b)] += 1
    except Exception:  # noqa: BLE001  (a template we cannot parse simply gives no palette)
        return None
    strong = [(c, n) for c, n in counts.items() if hls(c)[2] >= 0.25 and 0.12 <= hls(c)[1] <= 0.6]
    light = [
        (c, n)
        for c, n in counts.items()
        if hls(c)[1] >= 0.85 and hls(c)[2] >= 0.05 and c != "FFFFFF"
    ]
    if not strong:
        return None
    primary = max(strong, key=lambda x: x[1])[0]
    if light:
        tint = max(light, key=lambda x: x[1])[0]
    else:
        h, _, s = hls(primary)
        tint = _hex(*colorsys.hls_to_rgb(h, 0.93, min(s, 0.8)))
    return make_theme(primary, tint)


def extract_template_text(pdf: bytes, max_chars: int = 6000) -> str:
    """Per-page text of a template deck, to show the model its structure and wording."""
    out: list[str] = []
    try:
        reader = PdfReader(io.BytesIO(pdf))
        for i, page in enumerate(reader.pages[:MAX_PAGES_SCANNED], 1):
            text = re.sub(r"[ \t]+", " ", page.extract_text() or "").strip()
            if text:
                out.append(f"--- Page {i} ---\n{text}")
    except Exception:  # noqa: BLE001
        return ""
    return "\n".join(out)[:max_chars]

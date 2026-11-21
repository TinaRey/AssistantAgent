"""Pantalelle brand configuration, loaded from backend/assets/brand/brand.json."""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets" / "brand"
HEX = r"^[0-9A-Fa-f]{6}$"


class BrandColors(BaseModel):
    red: str = Field(pattern=HEX)
    peach: str = Field(pattern=HEX)  # title bars
    cover_panel: str = Field(pattern=HEX)
    text: str = Field(pattern=HEX)
    muted: str = Field(pattern=HEX)  # page numbers


class BrandContact(BaseModel):
    name: str | None = None
    role: str | None = None
    phone: str | None = None
    email: str | None = None


class Brand(BaseModel):
    colors: BrandColors
    font: str = "Calibri"
    mono_font: str = "Consolas"
    logo_file: str = "logo.png"
    cover_tag: str = "PRÉSENTATION"
    closing_title: str = "Merci pour votre attention"
    closing_lines: list[str] = []
    contact: BrandContact = BrandContact()
    assets_dir: Path = ASSETS_DIR

    @property
    def logo_path(self) -> Path:
        return self.assets_dir / self.logo_file


@lru_cache
def load_brand(directory: Path = ASSETS_DIR) -> Brand:
    data = json.loads((directory / "brand.json").read_text(encoding="utf-8"))
    data.pop("_comment", None)
    return Brand(**data, assets_dir=directory)

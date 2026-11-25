"""Unified PDF/image intake, rasterisation and page evidence."""
from dataclasses import dataclass
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageOps, ImageStat

from . import ocr

MAX_BYTES = 15 * 1024 * 1024
MAX_PAGES = 8
MAX_PIXELS = 24_000_000


@dataclass
class Page:
    number: int
    image: str
    width: int
    height: int
    words: list
    engine: str
    rotation: int = 0
    blank: bool = False
    low_resolution: bool = False


def pdf_words(source):
    xml = ocr.command(["pdftotext", "-bbox-layout", str(source), "-"])
    pages = []
    for page in ET.fromstring(xml).findall(".//{*}page"):
        width, height = float(page.get("width")), float(page.get("height"))
        pages.append([ocr.word(item.text, [float(item.get(key)) / axis for key, axis in
                      zip(("xMin", "yMin", "xMax", "yMax"), (width, height, width, height))], 1)
                      for item in page.findall(".//{*}word") if item.text])
    return pages


def images(source, dest):
    if source.suffix == ".pdf":
        info = ocr.command(["pdfinfo", str(source)]).decode(errors="replace")
        match = re.search(r"^Pages:\s+(\d+)", info, re.MULTILINE)
        if not match or not 1 <= int(match[1]) <= MAX_PAGES:
            raise ValueError(f"PDFs must contain 1–{MAX_PAGES} pages.")
        # A known maximum side also bounds memory for unusually sized PDFs.
        ocr.command(["pdftoppm", "-scale-to", "1500", "-png", str(source), str(dest / "render")], 60)
        return sorted(dest.glob("render-*.png")), pdf_words(source)
    return [source], []


def load_pages(source: Path, dest: Path):
    inputs, embedded = images(source, dest)
    result = []
    for number, path in enumerate(inputs, 1):
        with Image.open(path) as raw:
            if raw.width * raw.height > MAX_PIXELS:
                raise ValueError("Page image exceeds the pixel limit.")
            base = ImageOps.exif_transpose(raw).convert("RGB")
        low_resolution = min(base.size) < 700
        base.thumbnail((1800, 1800))
        target = dest / f"page-{number}.png"
        base.save(target)
        native_words = embedded[number - 1] if number <= len(embedded) else []
        blank = ImageStat.Stat(base.convert("L")).stddev[0] < 2
        rotation = 0
        if len(native_words) >= 8:
            words, engine = native_words, "poppler-embedded-text"
        elif blank:
            words, engine = [], "blank-page"
        else:
            words, engine = ocr.recognise(target, *base.size)
            score = ocr.orientation_score(words)
            if score < 48:
                candidate_path = dest / "rotation.png"
                for angle in (90, 180, 270):
                    candidate = base.rotate(angle, expand=True)
                    candidate.save(candidate_path)
                    candidate_words, _ = ocr.recognise(candidate_path, *candidate.size)
                    trial = ocr.orientation_score(candidate_words)
                    if trial > score + 1:
                        words, score, rotation = candidate_words, trial, angle
                candidate_path.unlink(missing_ok=True)
                if rotation:
                    base = base.rotate(rotation, expand=True)
                    base.save(target)
        result.append(Page(number, target.name, *base.size, words, engine, rotation, blank, low_resolution))
        if path.name.startswith("render-") and path.parent == dest:
            path.unlink()
    return result


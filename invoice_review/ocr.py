"""OCR adapters that never send documents over the network."""
import csv
import io
import json
import os
import re
import shutil
import subprocess
from functools import lru_cache

from .geometry import Word


def command(args, timeout=35):
    return subprocess.run(args, capture_output=True, check=True, timeout=timeout).stdout


def word(text, box, confidence):
    return Word(text, tuple(round(max(0.0, min(1.0, float(v))), 6) for v in box),
                max(0.0, min(1.0, float(confidence))))


@lru_cache(maxsize=1)
def backend():
    if executable := os.environ.get("INVOICE_VISION_OCR"):
        revision = command(["sw_vers", "-productVersion"]).decode().strip()
        return executable, f"apple-vision/macos-{revision}/accurate/en-US+en-GB"
    if executable := shutil.which("tesseract"):
        revision = command([executable, "--version"]).decode().splitlines()[0]
        return executable, f"{revision}/eng/psm11"
    raise RuntimeError("Install Tesseract or build the macOS Vision adapter first.")


def recognise(path, width, height):
    executable, revision = backend()
    if revision.startswith("apple-vision/"):
        rows = json.loads(command([executable, str(path)]))
        return [word(row["text"], row["box"], row["confidence"]) for row in rows], revision
    output = command([executable, str(path), "stdout", "-l", "eng", "--psm", "11", "tsv"])
    result = []
    for row in csv.DictReader(io.StringIO(output.decode()), delimiter="\t"):
        if row["level"] != "5" or not row["text"].strip():
            continue
        x, y, w, h = (int(row[key]) for key in ("left", "top", "width", "height"))
        result.append(word(row["text"], (x / width, y / height, (x + w) / width, (y + h) / height),
                           float(row["conf"]) / 100))
    return result, revision


def orientation_score(words):
    anchors = {"invoice", "subtotal", "total", "tax", "description", "quantity", "amount", "supplier"}
    tokens = [re.sub(r"[^a-z]", "", item.text.lower()) for item in words]
    score = 0.0
    for item, token in zip(words, tokens):
        if len(token) < 3:
            continue
        left, top, right, bottom = item.box
        # Vision can transcribe sideways glyphs while returning vertical boxes.
        # Score upright geometry before accepting a page orientation.
        horizontal = (right - left) >= (bottom - top) * 1.2
        if horizontal:
            score += item.confidence / 5 + (6 if token in anchors else 0)
            if token == "invoice" and top < .2:
                score += 5
        elif token in anchors:
            score -= 4
    return score


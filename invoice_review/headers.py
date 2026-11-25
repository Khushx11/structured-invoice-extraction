"""Extract labelled headers while retaining the exact matched token span."""
import re

from .geometry import field
from .normalise import CURRENCIES, normalise

ALIASES = {
    "supplier_name": ("supplier", "vendor", "issued by", "seller", "from"),
    "invoice_number": ("invoice number", "invoice no", "invoice id", "invoice #", "document number", "reference"),
    "invoice_date": ("invoice date", "issue date", "billing date", "date issued", "date"),
    "currency": ("currency", "billing currency"),
    "subtotal": ("subtotal", "sub total", "net amount", "items subtotal"),
    "tax": ("tax", "gst", "vat", "sales tax", "tax total"),
    "discount": ("discount", "less discount", "rebate"),
    "total": ("invoice total", "total payable", "amount due", "grand total", "balance due", "total"),
}


def label(text):
    return re.sub(r"[^a-z0-9#]+", " ", text.casefold()).strip()


def find_labels(row):
    for start in range(len(row)):
        for key, aliases in ALIASES.items():
            # Match long aliases before shorter aliases when the line starts at the same point.
            for length in range(min(3, len(row) - start), 0, -1):
                if label(" ".join(w.text for w in row[start:start + length])) in aliases:
                    yield start, start + length, key
                    break


def extract(rows, page, result, layout):
    for i, row in enumerate(rows):
        matches = list(find_labels(row))
        consumed = 0
        for start, end, key in sorted(matches, key=lambda match: (match[0], -match[1])):
            if start < consumed or (start > 0 and not layout):
                continue
            consumed = end
            if result[key]["value"] is not None:
                continue
            # Adjacent labels can share a line on two-column layouts.
            stop = min((next_start for next_start, _, _ in matches if next_start >= end), default=len(row)) if layout else len(row)
            words = row[end:stop]
            if layout and not words and key != "discount" and i + 1 < len(rows):
                next_row = rows[i + 1]
                gap = next_row[0].box[1] - row[-1].box[3]
                if 0 <= gap <= .045 and not list(find_labels(next_row)):
                    words = next_row
            if not words:
                continue
            # Amount labels sometimes carry punctuation/separators after the label.
            words = [word for word in words if word.text.strip(":|")]
            if not words:
                continue
            if key in {"subtotal", "tax", "total", "discount"}:
                words = words[-1:]
            if key == "currency":
                words = [word for word in words if word.text.upper() in CURRENCIES][:1] or words
            value = normalise(key, " ".join(word.text.strip(":") for word in words))
            if value is not None or result[key]["raw"] is None:
                result[key] = field(words, page, value)



"""Conservative English invoice normalisation."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

NUMBER = re.compile(r"(?:[+-]?[$€£]?\s*\d[\d,]*(?:\.\d+)?|\([$€£]?\d[\d,]*(?:\.\d+)?\))")
CURRENCIES = {"AUD", "USD", "NZD", "CAD", "GBP", "EUR", "SGD", "INR"}


def decimal_value(text):
    if text is None:
        return None
    value = str(text).strip()
    if len(value) > 22 or not NUMBER.fullmatch(value):
        return None
    negative = value.startswith("(")
    value = re.sub(r"[$€£,()\s]", "", value)
    try:
        number = Decimal(value)
        return format(-number if negative else number, "f")
    except InvalidOperation:
        return None


def normalise(key, value):
    if value is None or not str(value).strip():
        return None
    text = " ".join(str(value).split())
    if key in {"quantity", "unit_price", "line_amount", "subtotal", "tax", "discount", "total"}:
        return decimal_value(text)
    if key == "currency":
        return text.upper() if text.upper() in CURRENCIES else None
    if key == "invoice_date":
        for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                pass
        match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text)
        if match:
            first, second, year = map(int, match.groups())
            if first > 12 or second > 12 or first == second:
                month, day = (second, first) if first > 12 else (first, second)
                try:
                    return datetime(year, month, day).date().isoformat()
                except ValueError:
                    pass
        return None
    return text



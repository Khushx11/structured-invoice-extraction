"""Explain arithmetic differences with decimal cent rounding."""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def rounded(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def number(group, key):
    value = group[key]["value"]
    return Decimal(value) if value is not None else None


def reconcile(record):
    checks = []

    def compare(name, actual, expected, path):
        status = "unavailable" if actual is None or expected is None else (
            "pass" if rounded(actual) == rounded(expected) else "fail")
        checks.append({
            "name": name, "status": status, "path": path,
            "actual": str(rounded(actual)) if actual is not None else None,
            "expected": str(rounded(expected)) if expected is not None else None,
            "difference": str(rounded(actual) - rounded(expected)) if status != "unavailable" else None,
        })

    header = record["header"]
    amounts = []
    for index, row in enumerate(record["line_items"]):
        quantity, price, amount = (number(row, name) for name in
                                   ("quantity", "unit_price", "line_amount"))
        compare("Quantity × unit price", amount,
                quantity * price if quantity is not None and price is not None else None,
                f"line_items.{index}.line_amount")
        amounts.append(amount)
    subtotal, tax, discount, total = (number(header, key) for key in ("subtotal", "tax", "discount", "total"))
    compare("Subtotal = sum of line amounts", subtotal,
            sum(map(rounded, amounts), Decimal(0)) if amounts and None not in amounts else None,
            "header.subtotal")
    discount_field = header["discount"]
    if discount is None and discount_field["raw"] is None and discount_field["evidence"] is None:
        discount = Decimal(0)
    compare("Total = subtotal + tax − discount", total,
            subtotal + tax - discount if None not in (subtotal, tax, discount) else None,
            "header.total")
    return checks


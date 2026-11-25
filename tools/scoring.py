"""Invoice metrics and deterministic one-to-one row matching."""
from collections import Counter, defaultdict
from decimal import Decimal
from math import ceil
from statistics import mean

from invoice_review.normalise import normalise
from invoice_review.reconcile import reconcile
from invoice_review.schema import HEADER, ITEM

AMOUNTS = {"subtotal", "tax", "discount", "total", "quantity", "unit_price", "line_amount"}


def canonical(key, value):
    value = normalise(key, value)
    if value is None:
        return None
    return Decimal(value) if key in AMOUNTS else value.casefold() if key != "invoice_number" else value


def signature(item):
    return tuple(canonical(key, item[key]) for key in ITEM)


def row_matches(predicted, truth):
    return sum((Counter(map(signature, predicted)) & Counter(map(signature, truth))).values())


def flatten(record):
    return ({key: record["header"][key]["value"] for key in HEADER},
            [{key: item[key]["value"] for key in ITEM} for item in record["line_items"]])


def assess(extraction, truth, seconds):
    header, items = flatten(extraction)
    exact = {key: canonical(key, header[key]) == canonical(key, truth["header"][key]) for key in HEADER}
    tp = row_matches(items, truth["line_items"])
    errors = defaultdict(list)
    for key in ("subtotal", "tax", "discount", "total"):
        a, b = canonical(key, header[key]), canonical(key, truth["header"][key])
        if a is not None and b is not None:
            errors[key].append(float(abs(a - b)))
    # Pair by normalised description in occurrence order for amount error only.
    expected = defaultdict(list)
    for item in truth["line_items"]:
        expected[canonical("description", item["description"])].append(item)
    for item in items:
        choices = expected[canonical("description", item["description"])]
        if choices:
            other = choices.pop(0)
            for key in ("unit_price", "line_amount"):
                a, b = canonical(key, item[key]), canonical(key, other[key])
                if a is not None and b is not None:
                    errors[key].append(float(abs(a - b)))
    return {"extraction": extraction, "header_exact": exact, "tp": tp, "predicted": len(items),
            "expected": len(truth["line_items"]), "numeric_errors": errors, "seconds": seconds,
            "correct": all(exact.values()) and tp == len(items) == len(truth["line_items"]),
            "failed_reconciliation": any(item["status"] == "fail" for item in reconcile(extraction)),
            "unavailable_reconciliation": any(item["status"] == "unavailable" for item in reconcile(extraction))}


def summarise(rows):
    count, tp = len(rows), sum(row["tp"] for row in rows)
    predicted = sum(row["predicted"] for row in rows)
    expected = sum(row["expected"] for row in rows)
    amounts = defaultdict(list)
    for row in rows:
        for field, results in row["numeric_errors"].items():
            amounts[field].extend(results)
    times = sorted(row["seconds"] for row in rows)
    return {"invoices": count, "fully_correct": sum(row["correct"] for row in rows),
            "header_exact_match": {key: sum(row["header_exact"][key] for row in rows) / count for key in HEADER},
            "header_failures": {key: sum(not row["header_exact"][key] for row in rows) for key in HEADER},
            "line_rows": {"matches": tp, "predicted": predicted, "expected": expected,
                          "precision": tp / predicted if predicted else None,
                          "recall": tp / expected if expected else None},
            "numeric_error": {key: {"mae": mean(values), "pairs": len(values)} for key, values in amounts.items()},
            "reconciliation_failure_rate": sum(row["failed_reconciliation"] for row in rows) / count,
            "reconciliation_unavailable_rate": sum(row["unavailable_reconciliation"] for row in rows) / count,
            "p95_processing_seconds": times[ceil(.95 * count) - 1]}


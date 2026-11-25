"""Risk reasons and development-only threshold selection."""
from .reconcile import reconcile
from .schema import REQUIRED, ITEM

THRESHOLDS = (.50, .65, .75, .85, .90, .95, .98, 1.0, 1.01)


def readiness(record, threshold):
    fields = [(f"header.{key}", record["header"][key]) for key in REQUIRED]
    if record["header"]["discount"]["value"] is not None or record["header"]["discount"]["raw"]:
        fields.append(("header.discount", record["header"]["discount"]))
    fields += [(f"line_items.{i}.{key}", row[key]) for i, row in enumerate(record["line_items"]) for key in ITEM]
    reasons = {}
    for path, item in fields:
        if item["value"] is None:
            reasons[path] = "Missing or ambiguous value"
        elif item["evidence"] is None:
            reasons[path] = "Source region unavailable"
        elif item["evidence"]["ocr_confidence"] < threshold:
            reasons[path] = "OCR confidence below policy threshold"
    if not record["line_items"]:
        reasons["line_items"] = "No line items extracted"
    for check in reconcile(record):
        if check["status"] != "pass":
            reasons.setdefault(check["path"], f"{check['status'].title()} arithmetic check")
    return reasons


def operating_point(rows, threshold):
    accepted = [row for row in rows if not readiness(row["extraction"], threshold)]
    wrong = sum(not row["correct"] for row in accepted)
    return {"threshold": threshold, "total": len(rows), "accepted": len(accepted),
            "wrong_accepted": wrong, "coverage": len(accepted) / len(rows) if rows else 0,
            "routed_to_review": 1 - len(accepted) / len(rows) if rows else 0,
            "accepted_error": wrong / len(accepted) if accepted else None}


def select_threshold(rows, target_error=.05):
    feasible = [operating_point(rows, threshold) for threshold in THRESHOLDS]
    feasible = [point for point in feasible if point["accepted_error"] is not None
                and point["accepted_error"] <= target_error]
    return max(feasible, key=lambda point: (point["accepted"], point["threshold"]))["threshold"] if feasible else 1.01


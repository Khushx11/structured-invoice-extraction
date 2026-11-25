"""Immutable extraction lineage, review edits and approval decisions."""
from copy import deepcopy
from datetime import datetime, timezone

from .normalise import normalise
from .policy import readiness
from .reconcile import reconcile
from .schema import blank_item, get_field


def event(kind, **data):
    return {"event": kind, "at": datetime.now(timezone.utc).isoformat(), **data}


def start(extraction, threshold, *, filename, digest, pages, auto_approval=True):
    reasons = readiness(extraction, threshold)
    approved = auto_approval and not reasons
    record = {"status": "approved" if approved else "review", "revision": 0,
              "source": {"filename": filename, "sha256": digest},
              "original": deepcopy(extraction), "current": deepcopy(extraction), "pages": pages,
              "policy": {"threshold": threshold, "initial_reasons": reasons, "auto_approval_enabled": auto_approval},
              "history": [event("extracted", model=extraction["model"]),
                          event("auto_approved" if approved else "routed_to_review")]}
    return record


def change(record, action):
    if record["status"] != "review":
        raise ValueError("Approved records are read-only.")
    candidate = deepcopy(record)
    current = candidate["current"]
    operation = action.get("operation")
    if operation == "correct":
        path, raw = action.get("path", ""), action.get("value")
        if raw is not None and (not isinstance(raw, str) or len(raw) > 200):
            raise ValueError("Enter up to 200 characters per field.")
        item = get_field(current, path)
        value = normalise(path.rsplit(".", 1)[-1], raw)
        if raw and raw.strip() and value is None:
            raise ValueError("Enter a supported value or clear the field.")
        if item["value"] == value:
            raise ValueError("This field already has that value.")
        before = item["value"]
        item["value"] = value
        item["reviewer_value"] = raw
        candidate["history"].append(event("corrected", path=path, before=before, after=value))
    elif operation == "add_row":
        if len(current["line_items"]) >= 200:
            raise ValueError("This record already has 200 line items.")
        current["line_items"].append(blank_item())
        candidate["history"].append(event("added_line", index=len(current["line_items"]) - 1))
    elif operation == "remove_row":
        index = action.get("index")
        if type(index) is not int or not 0 <= index < len(current["line_items"]):
            raise ValueError("Unknown line item.")
        removed = current["line_items"].pop(index)
        candidate["history"].append(event("removed_line", index=index, before=removed))
    elif operation == "approve":
        note = action.get("note", "")
        if not isinstance(note, str) or len(note) > 500:
            raise ValueError("Enter a note of up to 500 characters.")
        reasons = readiness(current, candidate["policy"]["threshold"])
        if reasons and not note.strip():
            raise ValueError("Explain any remaining review flags before approval.")
        candidate["status"] = "approved"
        candidate["history"].append(event("approved", note=note.strip(), remaining_flags=reasons))
    else:
        raise ValueError("Unknown review operation.")
    candidate["revision"] += 1
    return candidate


def display(record):
    return {**record, "checks": reconcile(record["current"]),
            "flags": readiness(record["current"], record["policy"]["threshold"])}



"""Export only approved records."""
import csv
import io
import json

from .review import display
from .schema import ITEM


def export(record, kind):
    if record["status"] != "approved":
        raise ValueError("Approve this record before exporting it.")
    if kind == "json":
        return json.dumps(display(record), indent=2, ensure_ascii=False) + "\n"
    if kind != "csv":
        raise ValueError("Choose JSON or CSV.")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["line", *ITEM])
    for index, row in enumerate(record["current"]["line_items"], 1):
        values = [row[key]["value"] for key in ITEM]
        # Prevent formula interpretation for text fields in spreadsheet clients.
        description = values[0]
        if description and description.lstrip().startswith(("=", "+", "-", "@")):
            values[0] = "'" + description
        writer.writerow([index, *values])
    return stream.getvalue()


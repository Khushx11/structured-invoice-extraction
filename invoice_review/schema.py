"""Versioned extraction record and supported editor paths."""
from .geometry import field

SCHEMA = "1.0.0"
HEADER = ("supplier_name", "invoice_number", "invoice_date", "currency", "subtotal",
          "tax", "discount", "total")
REQUIRED = tuple(key for key in HEADER if key != "discount")
ITEM = ("description", "quantity", "unit_price", "line_amount")


def empty_extraction(model, ocr):
    return {"schema_version": SCHEMA, "model": model, "ocr": ocr,
            "header": {key: field() for key in HEADER}, "line_items": []}


def blank_item():
    return {key: field() for key in ITEM}


def get_field(extraction, path):
    parts = path.split(".")
    if len(parts) == 2 and parts[0] == "header" and parts[1] in HEADER:
        return extraction["header"][parts[1]]
    if (len(parts) == 3 and parts[0] == "line_items" and parts[1].isdigit()
            and parts[2] in ITEM):
        index = int(parts[1])
        if index < len(extraction["line_items"]):
            return extraction["line_items"][index][parts[2]]
    raise ValueError("Unknown field path")


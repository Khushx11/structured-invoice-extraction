"""Two table-reading strategies over shared OCR coordinates."""
from .geometry import field
from .headers import label
from .normalise import normalise
from .schema import ITEM

HEADING = {
    "description": {"description", "item", "service", "product", "details"},
    "quantity": {"quantity", "qty", "units"},
    "unit_price": {"price", "rate", "unitprice"},
    "line_amount": {"amount", "extended", "extension", "linetotal"},
}


def columns(row):
    found = {}
    for word in row:
        token = label(word.text)
        for name, aliases in HEADING.items():
            if token in aliases:
                found[name] = word.box[2]
    return found if set(found) == set(ITEM) else None


def is_footer(row):
    tokens = [label(word.text) for word in row[:3]]
    return bool(tokens and (tokens[0] in {"subtotal", "tax", "gst", "vat", "discount", "total", "payment", "terms", "notes", "page", "currency"}
                            or " ".join(tokens[:2]) in {"sub total", "net amount", "amount due", "grand total", "invoice total", "sales tax", "less discount", "tax total"}))


def make_item(cells, page):
    return {key: field(words, page, normalise(key, " ".join(w.text for w in words)))
            for key, words in cells.items()}


def rules_row(row, page):
    if len(row) < 4 or any(normalise(key, word.text) is None for key, word in zip(ITEM[1:], row[-3:])):
        return None
    return make_item(dict(zip(ITEM, (row[:-3], [row[-3]], [row[-2]], [row[-1]]))), page)


def layout_row(row, page, anchors):
    cells = {key: [] for key in ITEM}
    for word in row:
        key = min(ITEM[1:], key=lambda name: abs(anchors[name] - word.box[2]))
        if abs(anchors[key] - word.box[2]) <= .067 and normalise(key, word.text) is not None:
            cells[key].append(word)
        else:
            cells["description"].append(word)
    if not cells["description"] or not any(cells[key] for key in ITEM[1:]):
        return None
    return make_item(cells, page)


def extract(rows, page, layout, inherited):
    items = []
    anchors = inherited if layout else None
    for row in rows:
        if found := columns(row):
            anchors = found
        elif anchors and is_footer(row):
            anchors = None
        elif anchors:
            item = layout_row(row, page, anchors) if layout else rules_row(row, page)
            if item:
                items.append(item)
    return items, anchors


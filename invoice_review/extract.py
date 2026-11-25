"""Run either versioned extractor against identical page tokens."""
from .geometry import visual_rows
from .headers import extract as extract_headers
from .line_items import extract as extract_items
from .schema import empty_extraction

MODELS = {"rules": "ocr-rules/1.0.0", "layout": "ocr-spatial-columns/1.0.0"}


def extract(pages, method="layout"):
    layout = method == "layout"
    record = empty_extraction(MODELS[method], sorted({page.engine for page in pages}))
    columns = None
    for page in pages:
        rows = visual_rows(page.words)
        extract_headers(rows, page.number, record["header"], layout)
        items, columns = extract_items(rows, page.number, layout, columns)
        record["line_items"].extend(items)
    return record


"""Connect bounded ingestion, extraction and audit persistence."""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import shutil
from uuid import uuid4

from PIL import Image

from .documents import MAX_BYTES, load_pages
from .extract import extract
from .review import start

ALLOWED = {".pdf", ".png", ".jpg", ".jpeg"}


def ingest(store, filename, body, method, threshold):
    if not body or len(body) > MAX_BYTES:
        raise ValueError("Please supply a file up to 15 MiB.")
    filename = Path(filename).name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED:
        raise ValueError("Choose a PDF, PNG or JPEG.")
    if suffix == ".pdf" and not body.startswith(b"%PDF-"):
        raise ValueError("The uploaded file is not a PDF.")
    identifier = uuid4().hex
    directory = store.root / identifier
    directory.mkdir()
    try:
        source = directory / f"source{suffix}"
        source.write_bytes(body)
        if suffix != ".pdf":
            with Image.open(source) as image:
                if image.format not in {"PNG", "JPEG"}:
                    raise ValueError("Image content must be PNG or JPEG.")
        pages = load_pages(source, directory)
        if not pages:
            raise ValueError("No readable pages.")
        record = start(extract(pages, method), threshold, filename=filename, digest=sha256(body).hexdigest(),
                       pages=[asdict(page) for page in pages])
        store.insert(identifier, record)
        return identifier, record
    except BaseException:
        shutil.rmtree(directory)
        raise


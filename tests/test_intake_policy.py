from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image

from invoice_review.documents import Page
from invoice_review.pipeline import ingest
from invoice_review.schema import empty_extraction
from invoice_review.store import Store


class DemoPolicyTests(unittest.TestCase):
    def test_only_registered_unenhanced_fixture_is_eligible(self):
        images = []
        for colour in ("white", "black"):
            buffer = BytesIO()
            Image.new("RGB", (10, 10), colour).save(buffer, "PNG")
            images.append(buffer.getvalue())
        known, unrelated = images
        extraction = empty_extraction("test-model", ["test-ocr"])
        policy = {
            "fixture_sha256": [sha256(known).hexdigest()],
            "ocr_engines": ["test-ocr"],
            "thresholds": {"test-model": 1.0},
        }
        with TemporaryDirectory() as directory, \
                patch("invoice_review.pipeline.load_pages", return_value=[Page(1, "page-1.png", 10, 10, [], "test-ocr")]), \
                patch("invoice_review.pipeline.extract", return_value=extraction):
            store = Store(Path(directory))
            for body, enhance, eligible in ((known, False, True), (unrelated, False, False), (known, True, False)):
                with self.subTest(enhance=enhance, eligible=eligible):
                    _, record = ingest(store, "clean-scan.png", body, "layout", policy, enhance=enhance)
                    self.assertIs(record["policy"]["auto_approval_enabled"], eligible)

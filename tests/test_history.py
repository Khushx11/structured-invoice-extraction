from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from invoice_review.export import export
from invoice_review.review import change, start
from invoice_review.schema import empty_extraction
from invoice_review.store import Conflict, Store


class ReviewTests(unittest.TestCase):
    def test_correction_preserves_model_value_and_approval_requires_note(self):
        extracted = empty_extraction("rules/test", [])
        extracted["header"]["total"]["value"] = "99.00"
        record = start(extracted, 1.01, filename="example.png", digest="0" * 64, pages=[])
        updated = change(record, {"operation": "correct", "path": "header.total", "value": "104.00"})
        self.assertEqual(updated["original"]["header"]["total"]["value"], "99.00")
        self.assertEqual(updated["history"][-1]["before"], "99.00")
        self.assertEqual(updated["current"]["header"]["total"]["value"], "104.00")
        with self.assertRaises(ValueError):
            export(updated, "json")
        with self.assertRaises(ValueError):
            change(updated, {"operation": "approve"})
        approved = change(updated, {"operation": "approve", "note": "Reviewed from fictional source."})
        self.assertIn("104.00", export(approved, "json"))

    def test_stale_write_is_rejected(self):
        with TemporaryDirectory() as temp:
            store = Store(Path(temp))
            store.insert("test", start(empty_extraction("rules/test", []), 1.01,
                                      filename="file.pdf", digest="0" * 64, pages=[]))
            store.apply("test", 0, {"operation": "add_row"})
            with self.assertRaises(Conflict):
                store.apply("test", 0, {"operation": "add_row"})
            self.assertEqual(store.get("test")["revision"], 1)


from types import SimpleNamespace
import unittest

from invoice_review.extract import extract
from invoice_review.geometry import Word


def tokens(text):
    return [Word(word, (x, y, x + .025, y + .013), .97) for word, x, y in text]


class EvidenceTests(unittest.TestCase):
    def test_fields_point_to_the_correct_page_and_value(self):
        page = SimpleNamespace(number=3, engine="fixture", words=tokens([
            ("Invoice", .05, .10), ("number:", .10, .10), ("ABC-219", .29, .10),
            ("Description", .05, .30), ("Qty", .51, .30), ("Price", .69, .30), ("Amount", .87, .30),
            ("Packing", .05, .34), ("2", .51, .34), ("3.00", .69, .34), ("6.00", .87, .34),
        ]))
        record = extract([page])
        number = record["header"]["invoice_number"]
        self.assertEqual(number["raw"], "ABC-219")
        self.assertEqual(number["evidence"]["page"], 3)
        self.assertEqual(number["evidence"]["box"][0], .29)
        line = record["line_items"][0]["line_amount"]
        self.assertEqual(line["value"], "6.00")
        self.assertEqual(line["evidence"]["box"][0], .87)
        self.assertIsNone(record["header"]["tax"]["evidence"])


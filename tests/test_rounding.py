from decimal import Decimal
import unittest

from invoice_review.reconcile import reconcile, rounded
from invoice_review.schema import blank_item, empty_extraction


class ArithmeticTests(unittest.TestCase):
    def test_half_up_rounding_is_symmetric(self):
        self.assertEqual(rounded(Decimal("5.005")), Decimal("5.01"))
        self.assertEqual(rounded(Decimal("-5.005")), Decimal("-5.01"))

    def test_discount_and_missing_inputs(self):
        record = empty_extraction("test", [])
        row = blank_item()
        for key, value in (("quantity", "3"), ("unit_price", "1.005"), ("line_amount", "3.02")):
            row[key]["value"] = value
        record["line_items"] = [row]
        for key, value in (("subtotal", "3.02"), ("tax", "0.31"), ("discount", "0.15"), ("total", "3.18")):
            record["header"][key]["value"] = value
        self.assertEqual([check["status"] for check in reconcile(record)], ["pass"] * 3)
        record["header"]["tax"]["value"] = None
        self.assertEqual(reconcile(record)[-1]["status"], "unavailable")

    def test_large_accepted_operands_reconcile_without_decimal_overflow(self):
        record = empty_extraction("test", [])
        row = blank_item()
        for key in ("quantity", "unit_price"):
            row[key]["value"] = "9999999999999999999999"
        row["line_amount"]["value"] = "1"
        record["line_items"] = [row]
        check = reconcile(record)[0]
        self.assertEqual(check["status"], "fail")
        self.assertEqual(check["expected"], str(9999999999999999999999 ** 2) + ".00")

    def test_thousands_groups_must_be_complete(self):
        from invoice_review.normalise import decimal_value

        self.assertEqual(decimal_value("($1,234.50)"), "-1234.50")
        self.assertEqual(decimal_value("1234567.80"), "1234567.80")
        for malformed in ("1,23", "1234,567", "1,,000", "1,"):
            self.assertIsNone(decimal_value(malformed))

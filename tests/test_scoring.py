import unittest

from tools.scoring import row_matches


class RowMatchingTests(unittest.TestCase):
    def test_duplicates_are_matched_one_to_one(self):
        row = {"description": "Cable clips", "quantity": "2", "unit_price": "5.00", "line_amount": "10"}
        variant = dict(row, description=" cable  CLIPS ", line_amount="10.00")
        self.assertEqual(row_matches([row, row], [variant]), 1)

    def test_amount_mismatch_prevents_full_row_match(self):
        row = {"description": "Cable clips", "quantity": "2", "unit_price": "5", "line_amount": "10"}
        self.assertEqual(row_matches([dict(row, line_amount="11")], [row]), 0)


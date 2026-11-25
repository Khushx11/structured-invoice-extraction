from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from invoice_review.documents import load_pages
from invoice_review.extract import extract
from invoice_review.geometry import Word
from invoice_review.ocr import orientation_score
from tools.synthetic import invoice


class IntakeTests(unittest.TestCase):
    def test_upright_labels_score_better_than_sideways_labels(self):
        horizontal = Word("INVOICE", (.1, .05, .3, .08), 1)
        vertical = Word("INVOICE", (.05, .7, .08, .9), 1)
        self.assertGreater(orientation_score([horizontal]), orientation_score([vertical]))

    @unittest.skipUnless(all(shutil.which(tool) for tool in ("pdftotext", "pdftoppm", "pdfinfo")),
                         "Poppler tools are required for PDF integration")
    def test_digital_pdf_preserves_continuation_and_blank_pages(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            dest = root / "rendered"
            dest.mkdir()
            truth = invoice(root, 0, 2, second_page=True, blank=True)
            pages = load_pages(root / truth["path"], dest)
            self.assertEqual([page.number for page in pages], [1, 2, 3])
            self.assertTrue(pages[2].blank)
            actual = extract(pages)
            self.assertEqual(len(actual["line_items"]), 5)
            self.assertEqual(actual["line_items"][4]["line_amount"]["evidence"]["page"], 2)


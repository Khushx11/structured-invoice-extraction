from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from invoice_review.documents import scan_words
from invoice_review.geometry import Word
from invoice_review.quality import enhance_scan


class ScanQualityTests(unittest.TestCase):
    def test_flat_page_and_coordinate_dimensions_are_preserved(self):
        page = Image.new("RGB", (100, 200), (220, 220, 220))
        self.assertEqual(enhance_scan(page).tobytes(), page.tobytes())
        ImageDraw.Draw(page).rectangle((20, 25, 50, 40), fill=(190, 190, 190))
        self.assertEqual(enhance_scan(page).size, page.size)

    def test_enhanced_ocr_does_not_replace_the_displayed_source(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "page-2.png"
            image = Image.new("RGB", (120, 90), "white")
            ImageDraw.Draw(image).rectangle((10, 12, 40, 30), fill="#aaaaaa")
            image.save(path)
            before = path.read_bytes()
            evidence = [Word("12.34", (.1, .2, .3, .4), .92)]

            def fake_recognise(location, width, height):
                with Image.open(location) as transformed:
                    self.assertEqual(transformed.size, (width, height))
                self.assertNotEqual(location, path)
                return evidence, "test-ocr"

            with patch("invoice_review.documents.ocr.recognise", side_effect=fake_recognise):
                words, revision = scan_words(image, path, True)

            self.assertEqual(words, evidence)
            self.assertTrue(revision.endswith("/contrast-sharpness-v1"))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(path.parent.iterdir()), [path])

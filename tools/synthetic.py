"""Generate fictional invoices with supplier-template splits and rendered scans."""
import argparse
from decimal import Decimal
from io import BytesIO
import json
from pathlib import Path
import random
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import subprocess
from tempfile import TemporaryDirectory

from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas

LABELS = (
    ("Supplier", "Invoice number", "Invoice date", "Currency", "Subtotal", "Tax", "Discount", "Total"),
    ("Vendor", "Invoice No.", "Issue date", "Billing currency", "Net amount", "GST", "Rebate", "Amount due"),
    ("Seller", "Invoice ID", "Billing date", "Currency", "Sub total", "VAT", "Less discount", "Grand total"),
    ("Issued by", "Invoice #", "Date issued", "Currency", "Items subtotal", "Sales tax", "Discount", "Total payable"),
)
TEMPLATES = (
    ("Sample Alder Tools", "dev", 0, (67, 365, 445, 528), False),
    ("Sample Boreal Works", "dev", 1, (51, 330, 444, 546), True),
    ("Sample Cinder Studio", "dev", 2, (79, 356, 452, 533), False),
    ("Sample Drift Supplies", "test", 3, (58, 349, 427, 522), False),
    ("Sample Elm Repairs", "test", 0, (92, 412, 334, 530), True),
    ("Sample Fjord Paper", "test", 2, (39, 310, 432, 560), True),
    ("Sample Grove Parts", "test", 1, (66, 352, 436, 517), False),
    ("Sample Harbour Studio", "demo", 0, (58, 349, 440, 532), True),
)
ITEMS = ("Cable clips", "Desk brackets", "Paper sleeves", "Corner guards", "Panel fasteners",
         "Sample cartons", "Storage trays", "Blank labels", "Protective wraps", "Packing spacers")


def money(value):
    return format(value, ".2f")


def invoice(root, template, index, *, scanned=False, stress=None, second_page=False, blank=False, ambiguous=False):
    supplier, split, variant, columns, panel = TEMPLATES[template]
    rng = random.Random(1819 + template * 300 + index)
    slug = f"{split}-{template}-{index}" + (f"-{stress}" if stress else "")
    if split == "demo":
        slug = "ambiguous-scan" if ambiguous else "clean-scan"
    root.mkdir(parents=True, exist_ok=True)
    total_rows = 5 if second_page else 3
    lines = []
    for label in rng.sample(ITEMS, total_rows):
        qty = rng.randint(1, 5)
        price = Decimal(rng.randint(300, 2700)) / 100
        lines.append({"description": label, "quantity": str(qty), "unit_price": money(price),
                      "line_amount": money(price * qty)})
    subtotal = sum(Decimal(row["line_amount"]) for row in lines)
    tax = (subtotal / 10).quantize(Decimal(".01"))
    discount = Decimal(5) if index % 3 == 0 else Decimal(0)
    total = subtotal + tax - discount
    header = {"supplier_name": supplier, "invoice_number": f"INV-{template + 1}{index:03}",
              "invoice_date": f"2025-{(index % 9) + 1:02}-18", "currency": "AUD",
              "subtotal": money(subtotal), "tax": money(tax), "discount": money(discount),
              "total": money(total)}
    shown = [row.copy() for row in lines]
    if ambiguous:
        shown[0]["line_amount"] = money(Decimal(shown[0]["line_amount"]) + 5)
    # A genuinely different arrangement of headers, columns and typography per supplier.
    pdf = root / (slug + ".pdf")
    canvas = Canvas(str(pdf), pagesize=(595, 842), invariant=1)
    fonts = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("Fixture", str(fonts / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("FixtureBold", str(fonts / "VeraBd.ttf")))
    canvas.setTitle("Fictional invoice for extraction benchmark")
    palette = ("#1b3852", "#365856", "#564668", "#5c3c25")
    ink = palette[variant]
    left = columns[0]
    aliases = LABELS[variant]

    def heading(sheet):
        canvas.setFillColor(HexColor(ink))
        canvas.setFont("FixtureBold", 25)
        canvas.drawString(left, 784, "INVOICE")
        canvas.setFont("Fixture", 9)
        canvas.drawRightString(551, 790, "FICTIONAL TRAINING DOCUMENT")
        if sheet == 1:
            for i, (key, text) in enumerate(zip(tuple(header)[:4], aliases)):
                x = left if not panel or i % 2 == 0 else 345
                y = 745 - (i // 2 if panel else i) * 19
                canvas.setFont("Fixture", 12)
                canvas.drawString(x, y, f"{text}: {header[key]}")
        else:
            canvas.setFont("Fixture", 12)
            canvas.drawString(left, 743, "Line items continued")

    def table(rows):
        y = 632 + variant * 6
        canvas.setFillColor(HexColor("#e9eef3"))
        canvas.rect(left - 7, y - 6, 550 - left, 22, stroke=0, fill=1)
        canvas.setFillColor(HexColor(ink))
        canvas.setFont("FixtureBold", 11)
        canvas.drawString(left, y, ("Description", "Service", "Item", "Details")[variant])
        for x, text in zip(columns[1:], ("Qty", "Price", "Amount")):
            canvas.drawRightString(x, y, text)
        canvas.setFont("Fixture", 12)
        for row in rows:
            y -= 26
            canvas.drawString(left, y, row["description"])
            for x, key in zip(columns[1:], ("quantity", "unit_price", "line_amount")):
                canvas.drawRightString(x, y, money(Decimal(row[key])) if key == "quantity" else row[key])
        return y

    heading(1)
    y = table(shown[:3])
    if second_page:
        canvas.showPage()
        heading(2)
        y = table(shown[3:])
    canvas.setFont("FixtureBold", 12)
    for key, text in zip(tuple(header)[4:], aliases[4:]):
        y -= 24
        canvas.drawString(left + 125, y, text + ":")
        canvas.drawRightString(max(columns[1:]), y, header[key])
    canvas.showPage()
    if blank:
        canvas.showPage()
    canvas.save()
    if scanned or stress:
        with TemporaryDirectory() as scratch:
            prefix = Path(scratch) / "page"
            subprocess.run(["pdftoppm", "-scale-to", "1300", "-png", str(pdf), str(prefix)], check=True, capture_output=True)
            bitmaps = []
            for png in sorted(Path(scratch).glob("page-*.png")):
                with Image.open(png) as image:
                    image = image.convert("RGB")
                if stress == "rotated":
                    image = image.rotate(90, expand=True)
                elif stress == "faded":
                    image.thumbnail((570, 570))
                    image = ImageEnhance.Contrast(image.filter(ImageFilter.GaussianBlur(.85))).enhance(.44)
                bitmaps.append(image)
            if split == "demo":
                pdf.unlink()
                pdf = root / (slug + ".png")
                bitmaps[0].save(pdf)
            else:
                scan = BytesIO()
                bitmaps[0].save(scan, format="PDF", save_all=True, append_images=bitmaps[1:], resolution=150)
                pdf.write_bytes(scan.getvalue())
            for bitmap in bitmaps:
                bitmap.close()
    return {"id": slug, "path": pdf.name, "template": supplier, "split": "stress" if stress else split,
            "kind": "synthetic", "input": stress or ("scan" if scanned else "digital"),
            "header": header, "line_items": lines}


def generate(root, per_template=4):
    records = []
    for template in range(7):
        for i in range(per_template):
            records.append(invoice(root, template, i, scanned=i % 2 == 0,
                                   second_page=i == 2, blank=i == 3))
        if template >= 3:
            for i, stress in enumerate(("rotated", "faded"), 10):
                records.append(invoice(root, template, i, stress=stress, second_page=i == 11))
    (root / "manifest.json").write_text(json.dumps(records, indent=2) + "\n")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--per-template", type=int, default=4)
    args = parser.parse_args()
    if args.demo:
        rows = [invoice(args.output, 7, i, scanned=True, ambiguous=bool(i)) for i in range(2)]
        (args.output / "answers.json").write_text(json.dumps(rows, indent=2) + "\n")
    else:
        generate(args.output, args.per_template)


if __name__ == "__main__":
    main()



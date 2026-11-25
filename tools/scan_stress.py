"""Train with fictional blurred scans and test paired real FCC scan variants."""
import argparse
from collections import defaultdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from PIL import Image, ImageEnhance, ImageFilter
import pandas as pd

from invoice_review.geometry import visual_rows
from invoice_review.ocr import backend, command, recognise
from invoice_review.quality import enhance_scan
from .external_amounts import FIELDS, amount, hyperbots, measure, train, verified
from .synthetic import invoice

REVISION = "959e940da5f6344e2ee3d3e0af37781506d8360d"
INDEX_SHA = "fa40c083b63cf7b556eb30bef224d24ad03a0020970f639b7d463bea7a7d3881"
ROOT = "https://huggingface.co/datasets/amazon/ConfBench/resolve/" + REVISION
VARIANTS = ("original", "custom20")
LIMIT = 12


def render(pdf, folder):
    command(["pdftoppm", "-scale-to", "1500", "-png", str(pdf), str(folder / "raster")], 60)
    return sorted(folder.glob("raster-*.png"))


def blur(image):
    smaller = image.resize((max(1, image.width // 2), max(1, image.height // 2)), Image.Resampling.LANCZOS)
    degraded = ImageEnhance.Contrast(smaller.filter(ImageFilter.GaussianBlur(1.15))).enhance(.55)
    return degraded.resize(image.size, Image.Resampling.BICUBIC)


def ocr_text(paths, folder, transform):
    text = []
    for path in paths:
        with Image.open(path) as image:
            image = transform(image.convert("RGB"))
            scratch = folder / "ocr.png"
            image.save(scratch)
            words, _ = recognise(scratch, *image.size)
        text.extend(" ".join(word.text for word in row) for row in visual_rows(words))
    return "\n".join(text)


def download(cache, name):
    if not re.fullmatch(r"[0-9a-f]{32}__(?:original|custom20)\.pdf", name):
        raise ValueError("Unexpected ConfBench file name")
    path = cache / name
    if not path.is_file():
        with urlopen(f"{ROOT}/pdfs/{name}", timeout=45) as response:
            body = response.read(16 * 1024 * 1024 + 1)
        if len(body) > 16 * 1024 * 1024 or not body.startswith(b"%PDF-"):
            raise ValueError("Unexpected PDF response")
        temporary = path.with_suffix(".part")
        temporary.write_bytes(body)
        temporary.replace(path)
    return path


def paired_set(index):
    table = pd.read_parquet(BytesIO(verified(index, INDEX_SHA)))
    pairs = defaultdict(dict)
    for row in table.itertuples(index=False):
        if row.noise_variant not in VARIANTS or row.page_count > 3:
            continue
        net = row.json_response.get("NetAmountDue")
        if net is None:
            continue
        identifier = row.id.split("__")[0]
        pairs[identifier][row.noise_variant] = (row.id, amount(net))
    chosen = sorted((key for key, pair in pairs.items() if len(pair) == len(VARIANTS)),
                    key=lambda key: sha256(key.encode()).hexdigest())[:LIMIT]
    assert len(chosen) == LIMIT
    return [(key, pairs[key]) for key in chosen]


def augmented_training():
    found = []
    for template in range(3):
        for seed in range(30, 36):
            with TemporaryDirectory() as directory:
                root = Path(directory)
                truth = invoice(root, template, seed)
                paths = render(root / truth["path"], root)
                found.append((ocr_text(paths, root, blur),
                              {key: amount(truth["header"][key]) for key in FIELDS}))
    return found


def run(hyper_path, index, cache):
    groups, _ = hyperbots(hyper_path)
    clean_model = train(groups["train"])
    augmented = augmented_training()
    blur_model = train([*groups["train"], *augmented])
    cutoffs = {}
    for name, models in (("clean_model", clean_model), ("blur_model", blur_model)):
        cutoffs[name] = max((0, .25, .5, .75, .9), key=lambda cutoff: (
            measure(groups["dev"], ("total",), models, {"total": cutoff})["total"]["exact"], cutoff))
    cohorts = defaultdict(list)
    cache.mkdir(parents=True, exist_ok=True)
    sample = paired_set(index)
    source_digests = {}
    for key, variants in sample:
        assert variants["original"][1] == variants["custom20"][1]
        for variant, (name, target) in variants.items():
            with TemporaryDirectory() as directory:
                root = Path(directory)
                pdf = download(cache, name)
                source_digests[name] = sha256(pdf.read_bytes()).hexdigest()
                paths = render(pdf, root)
                transformations = [(variant, lambda image: image),
                                   (variant + "_enhanced", enhance_scan)]
                if variant == "original":
                    transformations += [("controlled_blur", blur),
                                        ("controlled_blur_enhanced", lambda image: enhance_scan(blur(image)))]
                for condition, transform in transformations:
                    text = ocr_text(paths, root, transform)
                    cohorts[condition].append((text, {"total": target}))
    result = {}
    for condition, rows in cohorts.items():
        result[condition] = {
            "label_rules": measure(rows, ("total",))["total"],
            "clean_model": measure(rows, ("total",), clean_model, {"total": cutoffs["clean_model"]})["total"],
            "blur_model": measure(rows, ("total",), blur_model, {"total": cutoffs["blur_model"]})["total"],
        }
    return {"model_revision": "ocr-text-amount-ranker/1.0.0",
            "ocr": backend()[1], "paired_real_documents": len(sample),
            "training_clean_documents": len(groups["train"]), "training_fictional_blur_documents": len(augmented),
            "selected_cutoffs": cutoffs, "dataset_revision": REVISION, "annotation_sha256": INDEX_SHA,
            "pdf_sha256": source_digests, "target": "NetAmountDue", "conditions": result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hyperbots", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.hyperbots, args.index, args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result["conditions"], indent=2))


if __name__ == "__main__":
    main()

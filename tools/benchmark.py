"""Measure extraction and automation policy on template-disjoint invoice cohorts."""
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from invoice_review.documents import load_pages
from invoice_review.extract import MODELS, extract
from invoice_review.policy import THRESHOLDS, operating_point, select_threshold
from .scoring import assess, summarise
from .synthetic import generate


def evaluate(root, manifest):
    groups = {split: {row["template"] for row in manifest if row["split"] == split}
              for split in ("dev", "test", "stress")}
    if not groups["dev"] or not groups["test"] or groups["dev"] & (groups["test"] | groups["stress"]):
        raise ValueError("Development templates must be disjoint from evaluation templates.")
    if len({item["id"] for item in manifest}) != len(manifest):
        raise ValueError("Repeated document IDs.")
    records = {method: {split: [] for split in groups} for method in MODELS}
    known_kinds = {row["kind"] for row in manifest}
    if known_kinds not in ({"synthetic"}, {"real"}):
        raise ValueError("Run real and synthetic documents separately.")
    engines = set()
    for truth in manifest:
        with TemporaryDirectory() as temp:
            started = perf_counter()
            pages = load_pages(root / truth["path"], Path(temp))
            elapsed = perf_counter() - started
            engines.update(page.engine for page in pages)
            for method in MODELS:
                started = perf_counter()
                result = extract(pages, method)
                elapsed_method = elapsed + perf_counter() - started
                records[method][truth["split"]].append(assess(result, truth, elapsed_method))
    methods = {}
    for method, batches in records.items():
        threshold = select_threshold(batches["dev"])
        all_points = {split: [operating_point(rows, t) for t in THRESHOLDS]
                      for split, rows in batches.items() if rows}
        methods[method] = {"model": MODELS[method], "selected_threshold": threshold,
                           "metrics": {split: summarise(rows) for split, rows in batches.items() if rows},
                           "operating_points": {split: next(p for p in points if p["threshold"] == threshold)
                                                for split, points in all_points.items()},
                           "coverage_error_curve": all_points}
    return {"kind": next(iter(known_kinds)), "ocr_engines": sorted(engines),
            "cohort_templates": {key: sorted(values) for key, values in groups.items()}, "methods": methods}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="Permission-cleared external manifest, with local relative paths")
    parser.add_argument("--output", type=Path, default=Path("results/synthetic.json"))
    parser.add_argument("--per-template", type=int, default=4)
    args = parser.parse_args()
    if args.manifest:
        report = evaluate(args.manifest.parent, json.loads(args.manifest.read_text()))
    else:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            report = evaluate(root, generate(root, args.per_template))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Measured {report['kind']} results in {args.output}")


if __name__ == "__main__":
    main()


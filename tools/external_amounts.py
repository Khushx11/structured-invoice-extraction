"""Train and compare amount extractors on publisher-provided invoice text."""
import argparse
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

HYPER_SHA = "9b9fdd5f83b9e1bb9311f9046e61770f1ee979b502b955afd4047dfb4e3e769d"
FCC_SHA = "c0fb260c58066c59cbcf2a42ad63a5d138adba2993629d154b4946f44af3846a"
FIELDS = ("subtotal", "tax", "total")
MONEY = re.compile(r"(?<![\d.,])[-−]?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}(?!\d)")
LABELS = {
    "subtotal": re.compile(r"\b(?:sub\s*total|net amount|gross total|gross amount)\b", re.I),
    "tax": re.compile(r"\b(?:sales tax|tax amount|vat|gst|hst)\b", re.I),
    "total": re.compile(r"\b(?:balance due|amount due|total due|total amount|grand total|net due)\b", re.I),
}
SPLITS = {"classic": "train", "modern": "train", "compact": "train", "two-column": "dev", "ledger": "test"}


def amount(value):
    if value is None:
        return None
    return Decimal(str(value).replace(",", "").replace("−", "-"))


def verified(path, digest):
    body = path.read_bytes()
    if sha256(body).hexdigest() != digest:
        raise ValueError(f"Publisher snapshot SHA-256 mismatch: {path.name}")
    return body


def seller_key(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def hyperbots(path):
    source = [json.loads(line) for line in verified(path, HYPER_SHA).splitlines()]
    owners = {}
    rank = {"train": 0, "dev": 1, "test": 2}
    for row in source:
        seller = seller_key(row["labels"]["entities"]["vendor_name"])
        split = SPLITS[row["layout"]]
        if rank[split] > rank.get(owners.get(seller), -1):
            owners[seller] = split
    result = defaultdict(list)
    for row in source:
        entities = row["labels"]["entities"]
        split = SPLITS[row["layout"]]
        seller = seller_key(entities["vendor_name"])
        if owners[seller] != split:
            continue
        truth = dict(zip(FIELDS, (amount(entities[key]) for key in ("subtotal", "tax_amount", "total_amount"))))
        result[split].append((row["ocr_text"], truth))
    return result, len(source) - sum(map(len, result.values()))


def fcc(path):
    from io import BytesIO

    table = pd.read_parquet(BytesIO(verified(path, FCC_SHA)))
    return [(row.text, {"total": amount(row.json_response["NetAmountDue"])})
            for row in table.itertuples(index=False) if row.json_response["NetAmountDue"] is not None], len(table)


@dataclass(frozen=True)
class Candidate:
    value: Decimal
    prefix: str
    prior: str
    location: int
    final_on_line: bool


def candidates(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        matches = list(MONEY.finditer(line))
        for match in matches:
            if line[match.end():].lstrip().startswith("%"):
                continue
            yield Candidate(amount(match.group()), line[:match.start()], lines[index - 1] if index else "",
                            min(9, index * 10 // len(lines)), match == matches[-1])


def features(item):
    def clean(value):
        return re.sub(r"\s+", " ", re.sub(r"[^a-z ]+", " ", value.casefold())).strip()

    prefix, prior = clean(item.prefix)[-70:], clean(item.prior)[-70:]
    output = {"position": item.location / 10, "final": int(item.final_on_line),
              **{f"label:{key}": int(bool(pattern.search(item.prefix))) for key, pattern in LABELS.items()}}
    for kind, text in (("line", prefix), ("above", prior)):
        for word in text.split():
            output[f"{kind}:word:{word}"] = 1
        for i in range(len(text) - 2):
            output[f"{kind}:tri:{text[i:i + 3]}"] = 1
    return output


def rule(items, key):
    return next((item.value for item in reversed(items)
                 if item.final_on_line and LABELS[key].search(item.prefix)), None)


def train(rows):
    features_all = []
    labels = {field: [] for field in FIELDS}
    for text, truth in rows:
        for item in candidates(text):
            features_all.append(features(item))
            for key in FIELDS:
                labels[key].append(int(item.value == truth[key]))
    return {key: make_pipeline(DictVectorizer(), LogisticRegression(max_iter=500, class_weight="balanced",
                                                                   random_state=42)).fit(features_all, labels[key])
            for key in FIELDS}


def ranked(model, items, cutoff):
    if not items:
        return None
    scores = model.predict_proba([features(item) for item in items])[:, 1]
    best = int(np.argmax(scores))
    return items[best].value if scores[best] >= cutoff else None


def measure(rows, keys, models=None, thresholds=None):
    counts = {key: {"n": 0, "exact": 0, "extracted": 0, "absolute_error": Decimal(0)} for key in keys}
    for text, gold in rows:
        items = list(candidates(text))
        for key in keys:
            actual = gold[key]
            if actual is None:
                continue
            result = counts[key]
            result["n"] += 1
            predicted = ranked(models[key], items, thresholds[key]) if models else rule(items, key)
            if predicted is not None:
                result["extracted"] += 1
                result["exact"] += int(predicted == actual)
                result["absolute_error"] += abs(predicted - actual)
    for result in counts.values():
        error = result.pop("absolute_error")
        result["exact_match"] = result["exact"] / result["n"] if result["n"] else None
        result["amount_mae_when_extracted"] = float(error / result["extracted"]) if result["extracted"] else None
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hyperbots", type=Path, required=True)
    parser.add_argument("--fcc", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, help="Optional destination for safe JSON model weights")
    args = parser.parse_args()
    groups, excluded = hyperbots(args.hyperbots)
    models = train(groups["train"])
    thresholds = {}
    for key in FIELDS:
        thresholds[key] = max((0, .25, .5, .75, .9), key=lambda value: (
            measure(groups["dev"], [key], models, {key: value})[key]["exact"], value))
    real, real_total = fcc(args.fcc)

    def results(rows, keys):
        return {"label_rules": measure(rows, keys), "learned_ranker": measure(rows, keys, models, thresholds)}

    report = {
        "model_revision": "ocr-text-amount-ranker/1.0.0",
        "source_hashes": {"hyperbots_jsonl_sha256": HYPER_SHA, "fcc_parquet_sha256": FCC_SHA},
        "hyperbots": {"counts": {key: len(value) for key, value in groups.items()},
                      "layouts": SPLITS, "supplier_overlap_rows_excluded": excluded,
                      "thresholds": thresholds, "dev": results(groups["dev"], FIELDS),
                      "test": results(groups["test"], FIELDS)},
        "fcc_external": {"source_documents": real_total, "documents_with_label": len(real),
                         "target": "NetAmountDue", **results(real, ("total",))},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if args.model:
        weights = {"revision": report["model_revision"], "thresholds": thresholds, "fields": {}}
        for key, model in models.items():
            vectoriser, classifier = model.steps[0][1], model.steps[1][1]
            weights["fields"][key] = {
                "intercept": float(classifier.intercept_[0]),
                "weights": dict(zip(vectoriser.get_feature_names_out().tolist(), classifier.coef_[0].tolist())),
            }
        args.model.parent.mkdir(parents=True, exist_ok=True)
        args.model.write_text(json.dumps(weights, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()



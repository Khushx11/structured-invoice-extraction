# External invoice amount benchmark

This experiment tests whether a learned amount ranker transfers across invoice layouts and from synthetic to real invoices. The browser's extraction and approval logic remains independent of this experiment.

## Datasets

- **Hyperbots Synthetic Invoice Extraction.** 200 generated English invoices with publisher-supplied OCR-style text and annotations, CC BY 4.0. Use revision `a86f2138061ae4499c0745040fa46d20afaa507f`. This project reads the subtotal, tax and total labels and uses the provided text as input. [Publisher and licence](https://huggingface.co/datasets/hyperbots-inc/synthetic-invoice-extraction)
- **Amazon RealKIE-FCC-Verified.** 75 real FCC broadcast advertising invoices with publisher-provided OCR text and corrected annotations, CC BY-NC 4.0. Use revision `3252a67a9c9da82e168eae518da8c860027c0a67`. Score the 68 invoices with a labelled NetAmountDue. The other seven are unscored. Use this data for non-commercial research. [Publisher, provenance and licence](https://huggingface.co/datasets/amazon-agi/RealKIE-FCC-Verified)

The download files are SHA-256 verified. Neither source text nor invoice images are committed. FCC is an independent transfer test and contributes no training, threshold selection or feature fitting. These are publisher-provided text benchmarks. Region mapping, fresh scanner OCR, full invoice accuracy and line items are outside this experiment.

## Method and measured results

Train and development splits use distinct layouts. Train on classic, modern and compact, select thresholds on two-column, and evaluate once on ledger. Exclude three repeated-supplier rows from the lower-priority split to keep normalised supplier names disjoint. This leaves 117 train, 40 development and 40 test invoices. All layouts share one synthetic generator.

The baseline selects an amount following an explicit label. The learned approach fits a weighted logistic ranker per field on the training partition using character trigrams, nearby words and relative position. Candidate supervision is derived from matching the labelled numeric value, so identical amounts can produce ambiguous training labels. The same confidence thresholds are frozen for both tests. Exact match includes abstentions as misses. MAE conditions on emitted values and does not penalise abstentions.

- **Hyperbots ledger test.** Both approaches found all 40 subtotals and all 40 tax amounts. The learned ranker found **40/40 totals** versus **30/40** with rules. The rules abstained on ten totals and had zero error on those it emitted.
- **Real FCC transfer.** The learned ranker found **8/68** net amounts due and emitted 23 predictions. Rules found **9/68** and emitted 13. Conditional MAE was **6,424.22** for the ranker and **4,276.92** for rules. The outcome does not support using the learned ranker for real invoice auto-acceptance.

[Aggregate metrics and exact source digests](../results/external-amounts.json)

## Reproduce

```sh
python -m pip install -r requirements-benchmark.txt
mkdir -p var/external
curl -fsSL 'https://huggingface.co/datasets/hyperbots-inc/synthetic-invoice-extraction/resolve/a86f2138061ae4499c0745040fa46d20afaa507f/data/test.jsonl' -o var/external/hyperbots.jsonl
curl -fsSL 'https://huggingface.co/datasets/amazon-agi/RealKIE-FCC-Verified/resolve/3252a67a9c9da82e168eae518da8c860027c0a67/data/test-00000-of-00001.parquet' -o var/external/fcc.parquet
python -m tools.external_amounts --hyperbots var/external/hyperbots.jsonl --fcc var/external/fcc.parquet --output var/external/metrics.json --model var/external/weights.json
```

The optional weights export contains numeric coefficients, feature names and cutoffs as JSON. It is trained entirely on the synthetic source.


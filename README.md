# Structured Invoice Extraction and Review

How much invoice processing can run without human review at a chosen observed error target? This project compares two extraction approaches and traces every supported field back to a specific page and region.

Upload an English PDF, PNG or JPEG, then inspect the extracted invoice beside its source. Review flags surface missing values and arithmetic discrepancies. Reviewers can correct fields, add or remove lines, approve records and export JSON or line-item CSV. The audit trail preserves the original extraction.

## Run locally

Install [Poppler and Tesseract](docs/deploy.md), then run:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m invoice_review.server
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The upload accepts up to eight PDF pages and 15 MiB. Files and review state stay in the local data directory. The default workflow requires an approval action for every invoice.

## Try the fictional demo

```sh
python -m tools.synthetic --output var/demo --demo
```

Upload `var/demo/clean-scan.png` and then `var/demo/ambiguous-scan.png`. Select **Locate Line 1 · Line amount** on the second invoice. Reconcile the displayed quantity and unit price, correct the amount to **84.96**, approve, and export both formats. See [the deployment guide](docs/deploy.md) for the macOS Vision adapter. With the same recorded OCR revision, `python -m invoice_review.server --demo-policy` enables the synthetic-calibrated auto-accept path for this demonstration.

## Benchmark and tests

```sh
python -m unittest discover -s tests -v
python -m tools.benchmark --output var/benchmark.json
python -m pip install matplotlib==3.10.6
python -m tools.plot_policy var/benchmark.json var/coverage-error.png
```

The spatial extractor auto-accepted **16 of 16** standard synthetic invoices and **4 of 8** degraded scans at the development-selected threshold. There were zero incorrect auto-accepts in those small cohorts. The rules baseline auto-accepted eight and two respectively. See [the measured results and plot](docs/evaluation.md) for matching definitions, p95, amount error and limitations.

For the optional browser regression and recording, install Playwright and its Chromium build with `npm install --no-save playwright@1.62.1` and `npx playwright install chromium`. Start the matching macOS Vision demo server and run `node tools/demo.cjs`. Set `INVOICE_DEMO_VIDEO=var/demo.webm` to record the captioned flow.

## Project documentation

- [Versioned schema and evidence coordinates](docs/schema.md)
- [Machine-readable approved record schema](schemas/invoice-v1.schema.json)
- [Dataset provenance and real-scan manifest format](docs/data.md)
- [Local deployment and limitations](docs/deploy.md)

This portfolio evaluation uses fictional documents only. The benchmark supports a separate permission-cleared real-scan manifest. The extraction revisions are deterministic text rules and spatial heuristics over revision-recorded OCR. Complex tables, unlabelled fields, atypical currencies and heavily degraded scans can require substantial manual review.


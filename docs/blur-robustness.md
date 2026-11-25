# Blurry-scan evaluation

Select **Try blur and contrast enhancement** when uploading a difficult scan. The app adjusts contrast and sharpness on the OCR copy and keeps the original preview and source coordinates. Enhanced scans require manual review. If an amount is unreadable, obtain a clearer source before approving it.

## Paired real-invoice experiment

[Amazon ConfBench](https://huggingface.co/datasets/amazon/ConfBench) is published under CC BY-NC 4.0. At the pinned revision in the metrics file, the benchmark selects 12 FCC broadcast-advertising invoices with net amounts due, complete original and photocopy pairs, and at most three pages. It runs fresh Apple Vision OCR on the original PDFs, publisher-provided photocopy/brightness variants (custom20), and controlled blur (half resolution, Gaussian blur and reduced contrast), each with and without enhancement. These invoices come from the same FCC collection as the external text benchmark. They are a paired stress test, so the two real-data evaluations cannot be counted as independent samples.

Both amount rankers train on 117 Hyperbots synthetic invoices. The blur-trained variant adds 18 fictional invoices from three development templates with freshly extracted OCR text after degradation. Both thresholds are selected on Hyperbots development data. FCC invoices are used only for testing. The OCR engine itself is fixed throughout.

Exact matches for net amount due out of 12 invoices per condition:

| Input | Label rules | Clean-trained ranker | Blur-trained ranker |
| --- | ---: | ---: | ---: |
| Original | 1 | 1 | 1 |
| Original, enhanced | 2 | 2 | 2 |
| Photocopy | 2 | 2 | 2 |
| Photocopy, enhanced | 1 | 1 | 1 |
| Controlled blur | 0 | 0 | 0 |
| Controlled blur, enhanced | 0 | 0 | 0 |

Blur augmentation improved none of the exact-match counts. Enhancement helped on originals and hurt on photocopies. The low baseline agreement on originals also shows substantial domain and extraction difficulties. This experiment evaluates one amount field on a small real sample. It does not measure full-record accuracy or establish blur robustness. The rankers are offline experiments.

## Reproduce

Follow [external dataset setup](external-data.md) for the pinned Hyperbots JSONL. Fetch the ConfBench annotations Parquet from the dataset tree at the revision recorded in [the measured results](../results/confbench-amounts.json). Set up the app dependencies, Poppler and the Apple Vision helper as described in the README. The command verifies the input snapshots and downloads the selected PDF pairs to a local cache. The repository contains aggregate metrics and input checksums.

```sh
python -m tools.scan_stress --hyperbots var/external/hyperbots.jsonl \
  --index var/external/confbench.parquet --cache var/external/confbench-pdfs \
  --output var/external/confbench-amounts.json
```

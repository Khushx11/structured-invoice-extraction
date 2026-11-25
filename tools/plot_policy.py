"""Plot held-out automation coverage against observed error."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def plot(report, target):
    figure, axes = plt.subplots(1, 2, figsize=(10, 4.2), layout="constrained", sharey=True)
    for axis, split in zip(axes, ("test", "stress")):
        for method, color, marker in (("rules", "#64518a", "s"), ("layout", "#146861", "o")):
            item = report["methods"][method]
            points = item["coverage_error_curve"].get(split, [])
            score_pairs = sorted({(100 * p["coverage"], 100 * p["accepted_error"])
                                  for p in points if p["accepted_error"] is not None})
            if score_pairs:
                x, y = zip(*score_pairs)
                axis.plot(x, y, marker=marker, color=color, label=method)
            selected = item["operating_points"].get(split)
            if selected and selected["accepted_error"] is not None:
                axis.scatter(100 * selected["coverage"], 100 * selected["accepted_error"],
                             facecolors="none", edgecolors=color, s=145, linewidths=1.5)
        axis.set(title="Held-out templates" if split == "test" else "Scan-quality stress",
                 xlabel="Automatically accepted invoices (%)", xlim=(-3, 103), ylim=(-3, 103))
        axis.grid(alpha=.24)
        if axis.lines:
            axis.legend(loc="upper left")
        else:
            axis.text(.5, .45, "No invoices accepted at the tested thresholds",
                      transform=axis.transAxes, ha="center", color="#52647a", fontsize=9)
    axes[0].set_ylabel("Incorrect among auto-accepted (%)")
    figure.suptitle("Synthetic invoice review policy · selected thresholds circled", fontweight="bold")
    figure.savefig(target, dpi=160)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    plot(json.loads(args.report.read_text()), args.output)


if __name__ == "__main__":
    main()


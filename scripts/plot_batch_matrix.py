#!/usr/bin/env python3
"""
Generate simple throughput/latency graphs for the latest batch-matrix runs.

The script expects the standard log names produced by scripts/run_batch_matrix.py.
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parent.parent


@dataclass
class RunSpec:
    name: str
    label: str
    threads: int
    log_path: Path


RUN_SPECS: List[RunSpec] = [
    RunSpec(
        name="baseline",
        label="Baseline OCC (8 threads)",
        threads=8,
        log_path=ROOT / "logs" / "batch_matrix_baseline.log",
    ),
    RunSpec(
        name="batch_sz8_wait200",
        label="Batch 8 / 200µs (8 threads, 6 validators)",
        threads=8,
        log_path=ROOT / "logs" / "batch_matrix_batch_sz8_wait200.log",
    ),
    RunSpec(
        name="batch_sz4_wait100",
        label="Batch 4 / 100µs (8 threads, 6 validators)",
        threads=8,
        log_path=ROOT / "logs" / "batch_matrix_batch_sz4_wait100.log",
    ),
    RunSpec(
        name="batch_sz16_wait500_thr16",
        label="Batch 16 / 500µs (16 threads, 16 validators)",
        threads=16,
        log_path=ROOT / "logs" / "batch_matrix_batch_sz16_wait500_thr16.log",
    ),
]


METRIC_PATTERNS: Dict[str, re.Pattern[str]] = {
    "agg_throughput": re.compile(r"agg_throughput:\s+([\d.]+)"),
    "avg_latency": re.compile(r"avg_latency:\s+([\d.]+)"),
    "agg_abort_rate": re.compile(r"agg_abort_rate:\s+([\d.]+)"),
    "n_commits": re.compile(r"n_commits:\s+([\d,]+)"),
    "batches_run": re.compile(r"\bbatches_run\s+:\s+(\d+)"),
    "txns_in_batches": re.compile(r"\btxns_in_batches\s+:\s+(\d+)"),
    "batch_committed_txns": re.compile(r"\bbatch_committed_txns\s+:\s+(\d+)"),
    "batch_aborted_txns": re.compile(r"\bbatch_aborted_txns\s+:\s+(\d+)"),
    "validation_threads": re.compile(r"\bvalidation_threads\s+:\s+(\d+)"),
}


def parse_metrics(log_file: Path) -> Dict[str, float]:
    text = log_file.read_text()

    def extract(pattern: re.Pattern[str], default: float = 0.0) -> float:
        match = pattern.search(text)
        if not match:
            return default
        raw = match.group(1).replace(",", "")
        return float(raw)

    metrics = {key: extract(pattern) for key, pattern in METRIC_PATTERNS.items()}
    return metrics


def build_dataset(run_specs: List[RunSpec]) -> List[Dict[str, float]]:
    dataset: List[Dict[str, float]] = []
    for run in run_specs:
        if not run.log_path.exists():
            raise FileNotFoundError(f"Missing log file: {run.log_path}")

        metrics = parse_metrics(run.log_path)
        metrics["n_commits"] = int(metrics.get("n_commits", 0))
        throughput = metrics.get("agg_throughput", 0.0)
        abort_rate = metrics.get("agg_abort_rate", 0.0)
        metrics["abort_per_1k"] = (abort_rate / throughput * 1000.0) if throughput else 0.0
        entry: Dict[str, float] = {
            "name": run.name,
            "label": run.label,
            "threads": run.threads,
            **metrics,
        }
        dataset.append(entry)
    return dataset


def _annotate_bars(ax, bars, fmt: str = "{:.0f}"):
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            fmt.format(height),
            xy=(bar.get_x() + bar.get_width() / 2.0, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )


def plot_summary(
    dataset: List[Dict[str, float]],
    output_path: Path,
    throughput_out: Optional[Path] = None,
    latency_out: Optional[Path] = None,
    abort_out: Optional[Path] = None,
) -> None:
    labels = [item["label"] for item in dataset]
    throughput = [item["agg_throughput"] for item in dataset]  # ops/s
    latency = [item["avg_latency"] for item in dataset]
    abort_metric = [item["abort_per_1k"] for item in dataset]

    fig, axes = plt.subplots(
        3, 1, figsize=(10, 10), sharex=True, constrained_layout=True
    )

    bar1 = axes[0].bar(range(len(labels)), throughput, color="#4c72b0")
    axes[0].set_ylabel("Throughput (ops/s)")
    axes[0].set_title("Batch Validation Tuning Summary")
    _annotate_bars(axes[0], bar1)

    bar2 = axes[1].bar(range(len(labels)), latency, color="#55a868")
    axes[1].set_ylabel("Avg latency (ms)")
    _annotate_bars(axes[1], bar2, fmt="{:.3f}")

    bar3 = axes[2].bar(range(len(labels)), abort_metric, color="#c44e52")
    axes[2].set_ylabel("Aborts per 1k txns")
    axes[2].set_xticks(range(len(labels)))
    axes[2].set_xticklabels(labels, rotation=15, ha="right")
    _annotate_bars(axes[2], bar3, fmt="{:.2f}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)

    if throughput_out:
        plt.figure(figsize=(8, 4))
        bars = plt.bar(range(len(labels)), throughput, color="#4c72b0")
        plt.ylabel("Throughput (ops/s)")
        plt.xticks(range(len(labels)), labels, rotation=15, ha="right")
        _annotate_bars(plt.gca(), bars)
        throughput_out.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(throughput_out, dpi=200)
        plt.close()

    if latency_out:
        plt.figure(figsize=(8, 4))
        bars = plt.bar(range(len(labels)), latency, color="#55a868")
        plt.ylabel("Avg latency (ms)")
        plt.xticks(range(len(labels)), labels, rotation=15, ha="right")
        _annotate_bars(plt.gca(), bars, fmt="{:.3f}")
        latency_out.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(latency_out, dpi=200)
        plt.close()

    if abort_out:
        plt.figure(figsize=(8, 4))
        bars = plt.bar(range(len(labels)), abort_metric, color="#c44e52")
        plt.ylabel("Aborts per 1k txns")
        plt.xticks(range(len(labels)), labels, rotation=15, ha="right")
        _annotate_bars(plt.gca(), bars, fmt="{:.2f}")
        abort_out.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        plt.savefig(abort_out, dpi=200)
        plt.close()


def plot_batch_only(dataset: List[Dict[str, float]], output_path: Path) -> None:
    batch_runs = [item for item in dataset if item["batches_run"] > 0]
    if not batch_runs:
        return

    labels = [item["label"] for item in batch_runs]
    batches = [item["batches_run"] for item in batch_runs]
    txns = [item["txns_in_batches"] for item in batch_runs]
    aborts = [item["batch_aborted_txns"] for item in batch_runs]

    fig, axes = plt.subplots(
        3, 1, figsize=(10, 9), sharex=True, constrained_layout=True
    )
    bar1 = axes[0].bar(range(len(labels)), batches, color="#8172b3")
    axes[0].set_ylabel("Batches processed")
    _annotate_bars(axes[0], bar1, fmt="{:,.0f}")

    bar2 = axes[1].bar(range(len(labels)), txns, color="#ccb974")
    axes[1].set_ylabel("Txns in batches")
    _annotate_bars(axes[1], bar2, fmt="{:,.0f}")

    bar3 = axes[2].bar(range(len(labels)), aborts, color="#64b5cd")
    axes[2].set_ylabel("Batch aborts (count)")
    axes[2].set_xticks(range(len(labels)))
    axes[2].set_xticklabels(labels, rotation=15, ha="right")
    _annotate_bars(axes[2], bar3)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "logs" / "plots",
        help="Base directory that will receive timestamped plot folders.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path for the main throughput/latency figure.",
    )
    parser.add_argument(
        "--batch-output",
        type=Path,
        default=None,
        help="Path for the batch-specific figure.",
    )
    parser.add_argument(
        "--throughput-output",
        type=Path,
        default=None,
        help="Path for the throughput-only figure.",
    )
    parser.add_argument(
        "--latency-output",
        type=Path,
        default=None,
        help="Path for the latency-only figure.",
    )
    parser.add_argument(
        "--abort-output",
        type=Path,
        default=None,
        help="Path for the abort-rate-only figure.",
    )
    args = parser.parse_args()

    base_dir = Path(args.output_dir).resolve()
    timestamp_dir = base_dir / datetime.now().strftime("%Y%m%d-%H%M%S")
    timestamp_dir.mkdir(parents=True, exist_ok=True)

    if args.output is None:
        args.output = timestamp_dir / "batch_matrix_summary.png"
    if args.batch_output is None:
        args.batch_output = timestamp_dir / "batch_matrix_batch_stats.png"
    if args.throughput_output is None:
        args.throughput_output = timestamp_dir / "batch_matrix_throughput.png"
    if args.latency_output is None:
        args.latency_output = timestamp_dir / "batch_matrix_latency.png"
    if args.abort_output is None:
        args.abort_output = timestamp_dir / "batch_matrix_abort_rate.png"

    dataset = build_dataset(RUN_SPECS)
    plot_summary(
        dataset,
        args.output,
        throughput_out=args.throughput_output,
        latency_out=args.latency_output,
        abort_out=args.abort_output,
    )
    plot_batch_only(dataset, args.batch_output)

    print("Wrote figures:")
    print(f" - {args.output}")
    if any(item["batches_run"] > 0 for item in dataset):
        print(f" - {args.batch_output}")
    print(f" - {args.throughput_output}")
    print(f" - {args.latency_output}")
    print(f" - {args.abort_output}")
    print(f"[plots saved under] {timestamp_dir}")


if __name__ == "__main__":
    main()


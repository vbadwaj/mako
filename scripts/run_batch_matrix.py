#!/usr/bin/env python3
"""
Run a short matrix of Mako OCC benchmarks (baseline + batch variants) and
summarize throughput/latency/abort/batch stats in a single table.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

RE_FLOAT = re.compile(r"([0-9][0-9_,\.]*)")


def _to_float(text: Optional[str]) -> float:
    if not text:
        return 0.0
    return float(text.replace(",", ""))


@dataclass
class RunSpec:
    name: str
    description: str
    num_threads: int = 8
    env: Dict[str, str] = field(default_factory=dict)
    log_path: Optional[Path] = None
    ok: bool = False
    stdout: str = ""
    agg_throughput: float = 0.0
    avg_latency_ms: float = 0.0
    agg_abort_rate: float = 0.0
    batches_run: int = 0
    txns_in_batches: int = 0
    batch_committed: int = 0
    batch_aborted: int = 0


def parse_metrics(run: RunSpec) -> None:
    text = run.stdout
    run.agg_throughput = _to_float(_search(text, r"agg_throughput:\s+([0-9,\.]+)\s+ops/sec"))
    run.avg_latency_ms = _to_float(_search(text, r"avg_latency:\s+([0-9,\.]+)\s+ms"))
    run.agg_abort_rate = _to_float(_search(text, r"agg_abort_rate:\s+([0-9,\.]+)\s+aborts/sec"))

    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() == "--- batch validation stats ---":
            stats = lines[idx + 1 : idx + 5]
            for stat_line in stats:
                _maybe_parse_batch_stat(run, stat_line)
            break


def _maybe_parse_batch_stat(run: RunSpec, line: str) -> None:
    if ":" not in line:
        return
    key, value = [part.strip() for part in line.split(":", 1)]
    if key == "batches_run":
        run.batches_run = int(_to_float(value))
    elif key == "txns_in_batches":
        run.txns_in_batches = int(_to_float(value))
    elif key == "batch_committed_txns":
        run.batch_committed = int(_to_float(value))
    elif key == "batch_aborted_txns":
        run.batch_aborted = int(_to_float(value))


def _search(text: str, pattern: str) -> Optional[str]:
    match = re.search(pattern, text)
    return match.group(1) if match else None


def run_dbtest(run: RunSpec, args: argparse.Namespace) -> None:
    log_dir = Path(args.log_dir).expanduser().resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"batch_matrix_{run.name}.log"
    env = os.environ.copy()
    env.update(
        {
            "OMP_NUM_THREADS": str(args.validation_threads),
            "MAKO_BATCH_VALIDATION_THREADS": str(args.validation_threads),
            "MAKO_ENABLE_BATCH_VALIDATION": "0",
            "BATCH_VALIDATION": "0",
            "MAKO_BATCH_VALIDATION_SIZE": "0",
            "MAKO_BATCH_VALIDATION_MAX_WAIT_US": "0",
        }
    )
    env.update(run.env)

    cmd = [
        str(Path(args.binary).resolve()),
        "--site-name",
        args.site_name,
        "--shard-config",
        args.shard_config,
        "--num-threads",
        str(run.num_threads),
    ]

    print(f"\n=== Running {run.name} ({run.description}) ===")
    process = subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    run.stdout = process.stdout
    log_path.write_text(run.stdout)
    run.log_path = log_path
    run.ok = process.returncode == 0
    if not run.ok:
        print(f"[WARN] Run '{run.name}' exited with code {process.returncode}. See {log_path}")
    else:
        print(f"[INFO] Log saved to {log_path}")


def print_table(runs: List[RunSpec]) -> None:
    headers = [
        "Run",
        "Threads",
        "Throughput (ops/s)",
        "Latency (ms)",
        "Abort/s",
        "Batches",
        "Batch txns",
        "Batch aborts",
    ]
    col_widths = [max(len(h), 14) for h in headers]

    def fmt_row(values: List[str]) -> str:
        return " | ".join(
            val.ljust(width) for val, width in zip(values, col_widths)
        )

    print("\n=== Summary ===")
    print(fmt_row(headers))
    print("-" * (sum(col_widths) + 3 * (len(headers) - 1)))

    for run in runs:
        values = [
            run.name,
            str(run.num_threads),
            f"{run.agg_throughput:,.0f}",
            f"{run.avg_latency_ms:.3f}",
            f"{run.agg_abort_rate:.2f}",
            f"{run.batches_run:,}",
            f"{run.txns_in_batches:,}",
            f"{run.batch_aborted:,}",
        ]
        print(fmt_row(values))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", default="build/dbtest", help="Path to dbtest binary")
    parser.add_argument("--site-name", default="local_s0")
    parser.add_argument("--shard-config", default="config/local-tpcc-baseline.yml")
    parser.add_argument("--log-dir", default="logs", help="Directory for run logs")
    parser.add_argument("--validation-threads", type=int, default=6, help="OMP_NUM_THREADS for validation")
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip the sequential baseline run",
    )
    args = parser.parse_args()

    runs: List[RunSpec] = []
    if not args.skip_baseline:
        runs.append(
            RunSpec(
                name="baseline",
                description="Sequential OCC",
                num_threads=8,
                env={
                    "MAKO_ENABLE_BATCH_VALIDATION": "0",
                    "BATCH_VALIDATION": "0",
                },
            )
        )

    runs.extend(
        [
            RunSpec(
                name="batch_sz8_wait200",
                description="Batch size 8, wait 200µs",
                num_threads=8,
                env={
                    "MAKO_ENABLE_BATCH_VALIDATION": "1",
                    "BATCH_VALIDATION": "1",
                    "MAKO_BATCH_VALIDATION_SIZE": "8",
                    "MAKO_BATCH_VALIDATION_MAX_WAIT_US": "200",
                },
            ),
            RunSpec(
                name="batch_sz4_wait100",
                description="Batch size 4, wait 100µs",
                num_threads=8,
                env={
                    "MAKO_ENABLE_BATCH_VALIDATION": "1",
                    "BATCH_VALIDATION": "1",
                    "MAKO_BATCH_VALIDATION_SIZE": "4",
                    "MAKO_BATCH_VALIDATION_MAX_WAIT_US": "100",
                },
            ),
            RunSpec(
                name="batch_sz16_wait500_thr16",
                description="16 threads, batch 16 wait 500µs",
                num_threads=16,
                env={
                    "MAKO_ENABLE_BATCH_VALIDATION": "1",
                    "BATCH_VALIDATION": "1",
                    "MAKO_BATCH_VALIDATION_SIZE": "16",
                    "MAKO_BATCH_VALIDATION_MAX_WAIT_US": "500",
                },
            ),
        ]
    )

    for run in runs:
        run_dbtest(run, args)
        parse_metrics(run)

    print_table(runs)

    print("\nLogs:")
    for run in runs:
        status = "OK" if run.ok else "FAILED"
        print(f" - {run.name:<24} [{status}] {run.log_path}")


if __name__ == "__main__":
    main()



#!/usr/bin/env python3
"""
Run the batch-validation matrix on a multi-shard deployment, aggregate the
metrics across all shards, and emit synthetic logs so the existing plotting
script can generate graphs.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


RE_FLOAT = re.compile(r"([0-9][0-9_,\.]*)")


def _to_float(text: Optional[str]) -> float:
    if not text:
        return 0.0
    return float(text.replace(",", ""))


def _to_int(text: Optional[str]) -> int:
    if not text:
        return 0
    return int(text.replace(",", ""))


def _search(pattern: str, text: str) -> Optional[str]:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1) if match else None


def _multi_search(pattern: str, text: str) -> List[str]:
    return re.findall(pattern, text, re.MULTILINE)


@dataclass
class RunSpec:
    name: str
    description: str
    num_threads: int = 8
    env: Dict[str, str] = field(default_factory=dict)
    validation_threads: Optional[int] = None
    scale_factor: Optional[int] = None


@dataclass
class ShardMetrics:
    agg_throughput: float
    avg_latency_ms: float
    agg_abort_rate: float
    n_commits: int
    batches_run: int
    txns_in_batches: int
    batch_committed: int
    batch_aborted: int
    batch_requests: int
    commit_attempts: int
    batches_used: int
    avg_collection_wait_us: float
    avg_validation_time_us: float
    avg_trigger_wait_us: float
    flush_full_count: int
    flush_timeout_count: int
    max_batch_size_observed: int
    batch_size: int
    max_wait_us: int
    validation_threads: int


@dataclass
class AggregateMetrics:
    name: str
    description: str
    num_threads: int
    log_path: Path
    agg_throughput: float
    avg_latency_ms: float
    agg_abort_rate: float
    n_commits: int
    batches_run: int
    txns_in_batches: int
    batch_committed: int
    batch_aborted: int
    batch_requests: int
    commit_attempts: int
    batches_used: int
    avg_collection_wait_us: float
    avg_validation_time_us: float
    avg_trigger_wait_us: float
    flush_full_count: int
    flush_timeout_count: int
    max_batch_size_observed: int
    batch_size: int
    max_wait_us: int
    validation_threads: int


def parse_shard_metrics(log_text: str) -> ShardMetrics:
    agg_throughput = _to_float(_search(r"agg_throughput:\s+([0-9,\.]+)\s+ops/sec", log_text))
    avg_latency_ms = _to_float(_search(r"avg_latency:\s+([0-9,\.]+)\s+ms", log_text))
    agg_abort_rate = _to_float(_search(r"agg_abort_rate:\s+([0-9,\.]+)\s+aborts/sec", log_text))
    n_commits = _to_int(_search(r"n_commits:\s+([0-9,]+)", log_text))

    batches = _multi_search(r"\bbatches_run\s+:\s+([0-9,]+)", log_text)
    txns = _multi_search(r"\btxns_in_batches\s+:\s+([0-9,]+)", log_text)
    committed = _multi_search(r"\bbatch_committed_txns\s+:\s+([0-9,]+)", log_text)
    aborted = _multi_search(r"\bbatch_aborted_txns\s+:\s+([0-9,]+)", log_text)

    def _first_int(matches: List[str]) -> int:
        return _to_int(matches[0]) if matches else 0

    batches_run = _first_int(batches)
    txns_in_batches = _first_int(txns)
    batch_committed = _first_int(committed)
    batch_aborted = _first_int(aborted)

    batch_requests = _to_int(_search(r"batch_requests\s+:\s+([0-9,]+)", log_text))
    commit_attempts = _to_int(_search(r"commit_attempts\s+:\s+([0-9,]+)", log_text))
    batches_used = _to_int(_search(r"batches_used\s+:\s+([0-9,]+)", log_text))
    avg_collection = _to_float(_search(r"avg_collection_wait_us\s+:\s+([0-9,\.]+)", log_text))
    avg_validation = _to_float(_search(r"avg_validation_time_us\s+:\s+([0-9,\.]+)", log_text))
    avg_trigger = _to_float(_search(r"avg_trigger_wait_us\s+:\s+([0-9,\.]+)", log_text))
    flush_full = _to_int(_search(r"flush_full_count\s+:\s+([0-9,]+)", log_text))
    flush_timeout = _to_int(_search(r"flush_timeout_count\s+:\s+([0-9,]+)", log_text))
    max_batch_observed = _to_int(_search(r"max_batch_size_observed\s*:\s*([0-9,]+)", log_text))
    batch_size = _to_int(_search(r"batch_size\s+:\s+([0-9,]+)", log_text))
    max_wait_us = _to_int(_search(r"max_wait_us\s+:\s+([0-9,]+)", log_text))
    validation_threads = _to_int(_search(r"validation_threads\s+:\s+([0-9,]+)", log_text))

    return ShardMetrics(
        agg_throughput=agg_throughput,
        avg_latency_ms=avg_latency_ms,
        agg_abort_rate=agg_abort_rate,
        n_commits=n_commits,
        batches_run=batches_run,
        txns_in_batches=txns_in_batches,
        batch_committed=batch_committed,
        batch_aborted=batch_aborted,
        batch_requests=batch_requests,
        commit_attempts=commit_attempts,
        batches_used=batches_used,
        avg_collection_wait_us=avg_collection,
        avg_validation_time_us=avg_validation,
        avg_trigger_wait_us=avg_trigger,
        flush_full_count=flush_full,
        flush_timeout_count=flush_timeout,
        max_batch_size_observed=max_batch_observed,
        batch_size=batch_size,
        max_wait_us=max_wait_us,
        validation_threads=validation_threads,
    )


def combine_metrics(
    name: str,
    description: str,
    num_threads: int,
    log_path: Path,
    shard_metrics: List[ShardMetrics],
) -> AggregateMetrics:
    total_throughput = sum(s.agg_throughput for s in shard_metrics)
    total_commits = sum(s.n_commits for s in shard_metrics)
    if total_commits:
        avg_latency = sum(s.avg_latency_ms * s.n_commits for s in shard_metrics) / total_commits
    else:
        avg_latency = 0.0
    total_abort_rate = sum(s.agg_abort_rate for s in shard_metrics)

    batches_run = sum(s.batches_run for s in shard_metrics)
    txns_in_batches = sum(s.txns_in_batches for s in shard_metrics)
    batch_committed = sum(s.batch_committed for s in shard_metrics)
    batch_aborted = sum(s.batch_aborted for s in shard_metrics)
    batch_requests = sum(s.batch_requests for s in shard_metrics)
    commit_attempts = sum(s.commit_attempts for s in shard_metrics)
    batches_used = sum(s.batches_used for s in shard_metrics)

    def _weighted_average(field: str, weight_field: str) -> float:
        numerator = 0.0
        denominator = 0
        for s in shard_metrics:
            value = getattr(s, field)
            weight = getattr(s, weight_field)
            numerator += value * weight
            denominator += weight
        return numerator / denominator if denominator else 0.0

    avg_collection = _weighted_average("avg_collection_wait_us", "batches_run")
    avg_validation_time = _weighted_average("avg_validation_time_us", "batches_run")
    avg_trigger = _weighted_average("avg_trigger_wait_us", "batches_run")
    flush_full = sum(s.flush_full_count for s in shard_metrics)
    flush_timeout = sum(s.flush_timeout_count for s in shard_metrics)
    max_batch_observed = max((s.max_batch_size_observed for s in shard_metrics), default=0)

    # assume identical settings across shards
    batch_size = shard_metrics[0].batch_size if shard_metrics else 0
    max_wait_us = shard_metrics[0].max_wait_us if shard_metrics else 0
    validation_threads = shard_metrics[0].validation_threads if shard_metrics else 0

    return AggregateMetrics(
        name=name,
        description=description,
        num_threads=num_threads,
        log_path=log_path,
        agg_throughput=total_throughput,
        avg_latency_ms=avg_latency,
        agg_abort_rate=total_abort_rate,
        n_commits=total_commits,
        batches_run=batches_run,
        txns_in_batches=txns_in_batches,
        batch_committed=batch_committed,
        batch_aborted=batch_aborted,
        batch_requests=batch_requests,
        commit_attempts=commit_attempts,
        batches_used=batches_used,
        avg_collection_wait_us=avg_collection,
        avg_validation_time_us=avg_validation_time,
        avg_trigger_wait_us=avg_trigger,
        flush_full_count=flush_full,
        flush_timeout_count=flush_timeout,
        max_batch_size_observed=max_batch_observed,
        batch_size=batch_size,
        max_wait_us=max_wait_us,
        validation_threads=validation_threads,
    )


def write_synthetic_log(metrics: AggregateMetrics, shard_logs: List[Tuple[str, Path]]) -> None:
    lines = [
        f"=== aggregated summary: {metrics.name} ===",
        f"agg_throughput: {metrics.agg_throughput:,.1f} ops/sec",
        f"avg_latency: {metrics.avg_latency_ms:.6f} ms",
        f"agg_abort_rate: {metrics.agg_abort_rate:.4f} aborts/sec",
        f"n_commits: {metrics.n_commits:,}",
        "--- batch validation stats ---",
        f"  batches_run          : {metrics.batches_run:,}",
        f"  txns_in_batches      : {metrics.txns_in_batches:,}",
        f"  batch_committed_txns : {metrics.batch_committed:,}",
        f"  batch_aborted_txns   : {metrics.batch_aborted:,}",
        "--- sto batch validation stats ---",
        "  enabled                : true",
        f"  batch_size             : {metrics.batch_size}",
        f"  max_wait_us            : {metrics.max_wait_us}",
        f"  validation_threads     : {metrics.validation_threads}",
        f"  batches_run            : {metrics.batches_run:,}",
        f"  txns_in_batches        : {metrics.txns_in_batches:,}",
        f"  batch_committed_txns   : {metrics.batch_committed:,}",
        f"  batch_aborted_txns     : {metrics.batch_aborted:,}",
        f"  commit_attempts        : {metrics.commit_attempts:,}",
        f"  batch_requests         : {metrics.batch_requests:,}",
        f"  batches_used           : {metrics.batches_used:,}",
        f"  avg_collection_wait_us : {metrics.avg_collection_wait_us:.0f}",
        f"  avg_validation_time_us : {metrics.avg_validation_time_us:.0f}",
        f"  avg_trigger_wait_us    : {metrics.avg_trigger_wait_us:.0f}",
        f"  flush_full_count       : {metrics.flush_full_count:,}",
        f"  flush_timeout_count    : {metrics.flush_timeout_count:,}",
        f"  max_batch_size_observed: {metrics.max_batch_size_observed}",
        "",
        "=== shard log references ===",
    ]
    for label, path in shard_logs:
        lines.append(f"{label}: {path}")
    metrics.log_path.write_text("\n".join(lines) + "\n")


def run_sharded_process(
    binary: Path,
    shard_config: Path,
    site_name: str,
    shard_index: int,
    num_threads: int,
    env: Dict[str, str],
    log_path: Path,
) -> subprocess.Popen:
    cmd = [
        str(binary),
        "--shard-config",
        str(shard_config),
        "--site-name",
        site_name,
        "--shard-index",
        str(shard_index),
        "--num-threads",
        str(num_threads),
    ]
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )

    def _close_file(process: subprocess.Popen, handle):
        def _wait_and_close():
            process.wait()
            handle.close()

        return _wait_and_close

    proc._close_handler = _close_file(proc, log_file)  # type: ignore[attr-defined]
    return proc


def wait_process(proc: subprocess.Popen) -> int:
    ret = proc.wait()
    close_handler = getattr(proc, "_close_handler", None)
    if callable(close_handler):
        close_handler()
    return ret


def run_matrix(args: argparse.Namespace) -> List[AggregateMetrics]:
    binary = Path(args.binary).resolve()
    shard_config = Path(args.shard_config).resolve()
    log_dir = Path(args.log_dir).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)

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
                name="batch_sz16_wait300_thr16",
                description="Batch size 16, wait 300µs, 16 clients",
                num_threads=16,
                env={
                    "MAKO_ENABLE_BATCH_VALIDATION": "1",
                    "BATCH_VALIDATION": "1",
                    "MAKO_BATCH_VALIDATION_SIZE": "16",
                    "MAKO_BATCH_VALIDATION_MAX_WAIT_US": "300",
                },
            ),
            RunSpec(
                name="batch_sz16_wait200_thr24",
                description="Batch size 16, wait 200µs, 24 clients",
                num_threads=24,
                validation_threads=8,
                env={
                    "MAKO_ENABLE_BATCH_VALIDATION": "1",
                    "BATCH_VALIDATION": "1",
                    "MAKO_BATCH_VALIDATION_SIZE": "16",
                    "MAKO_BATCH_VALIDATION_MAX_WAIT_US": "200",
                },
            ),
            RunSpec(
                name="batch_sz16_wait150_thr24",
                description="Batch size 16, wait 150µs, 24 clients",
                num_threads=24,
                validation_threads=8,
                env={
                    "MAKO_ENABLE_BATCH_VALIDATION": "1",
                    "BATCH_VALIDATION": "1",
                    "MAKO_BATCH_VALIDATION_SIZE": "16",
                    "MAKO_BATCH_VALIDATION_MAX_WAIT_US": "150",
                },
            ),
            RunSpec(
                name="batch_sz32_wait300_thr24",
                description="Batch size 32, wait 300µs, 24 clients",
                num_threads=24,
                validation_threads=12,
                env={
                    "MAKO_ENABLE_BATCH_VALIDATION": "1",
                    "BATCH_VALIDATION": "1",
                    "MAKO_BATCH_VALIDATION_SIZE": "32",
                    "MAKO_BATCH_VALIDATION_MAX_WAIT_US": "300",
                },
            ),
        ]
    )

    sites = args.sites
    if not sites:
        raise ValueError("At least one site must be provided via --sites")

    aggregates: List[AggregateMetrics] = []

    for run in runs:
        print(f"\n=== Running {run.name} ({run.description}) ===")
        run_validation_threads = (
            run.validation_threads
            if run.validation_threads is not None
            else args.validation_threads
        )
        run_scale_factor = (
            run.scale_factor if run.scale_factor is not None else args.scale_factor
        )
        env = os.environ.copy()
        env.update(
            {
                "OMP_NUM_THREADS": str(run_validation_threads),
                "MAKO_BATCH_VALIDATION_THREADS": str(run_validation_threads),
                "MAKO_SCALE_FACTOR": str(run_scale_factor),
                "MAKO_ENABLE_BATCH_VALIDATION": "0",
                "BATCH_VALIDATION": "0",
                "MAKO_BATCH_VALIDATION_SIZE": "0",
                "MAKO_BATCH_VALIDATION_MAX_WAIT_US": "0",
            }
        )
        env.update(run.env)

        combined_log = log_dir / f"batch_matrix_{run.name}.log"
        shard_logs: List[Path] = []
        procs: List[subprocess.Popen] = []
        for idx, site_name in enumerate(sites):
            shard_log = log_dir / f"batch_matrix_{run.name}_shard{idx}.log"
            shard_logs.append(shard_log)
            proc = run_sharded_process(
                binary,
                shard_config,
                site_name,
                idx,
                run.num_threads,
                env,
                shard_log,
            )
            procs.append(proc)

        exit_codes = [wait_process(proc) for proc in procs]
        if any(code != 0 for code in exit_codes):
            code_str = ", ".join(
                f"shard{idx}={code}" for idx, code in enumerate(exit_codes)
            )
            log_str = ", ".join(
                f"shard{idx}: {path}" for idx, path in enumerate(shard_logs)
            )
            print(
                f"[WARN] Run '{run.name}' exited with codes {code_str}. Logs: {log_str}"
            )

        shard_metrics = [
            parse_shard_metrics(shard_log.read_text()) for shard_log in shard_logs
        ]

        aggregate = combine_metrics(
            run.name,
            run.description,
            run.num_threads,
            combined_log,
            shard_metrics,
        )
        write_synthetic_log(
            aggregate,
            [(f"shard{idx}", shard_log) for idx, shard_log in enumerate(shard_logs)],
        )
        aggregates.append(aggregate)
        print(f"[INFO] Aggregated log saved to {combined_log}")

    return aggregates


def print_table(results: List[AggregateMetrics]) -> None:
    headers = [
        "Run",
        "Threads/Shard",
        "Throughput (ops/s)",
        "Latency (ms)",
        "Abort/s",
        "Batches",
        "Batch txns",
        "Batch aborts",
    ]
    col_widths = [max(len(h), 16) for h in headers]

    def fmt_row(values: List[str]) -> str:
        return " | ".join(
            val.ljust(width) for val, width in zip(values, col_widths)
        )

    print("\n=== Summary (aggregated across all shards) ===")
    print(fmt_row(headers))
    print("-" * (sum(col_widths) + 3 * (len(headers) - 1)))

    for result in results:
        values = [
            result.name,
            str(result.num_threads),
            f"{result.agg_throughput:,.0f}",
            f"{result.avg_latency_ms:.3f}",
            f"{result.agg_abort_rate:.2f}",
            f"{result.batches_run:,}",
            f"{result.txns_in_batches:,}",
            f"{result.batch_aborted:,}",
        ]
        print(fmt_row(values))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", default="build/dbtest", help="Path to dbtest binary")
    parser.add_argument("--shard-config", default="config/local-shards2-warehouses1.yml")
    parser.add_argument(
        "--sites",
        nargs="+",
        default=["s0_leader", "s1_leader"],
        help="Space-separated site names; order defines shard indices",
    )
    parser.add_argument("--log-dir", default="logs/sharded", help="Directory for log output")
    parser.add_argument(
        "--validation-threads",
        type=int,
        default=6,
        help="OMP_NUM_THREADS / MAKO_BATCH_VALIDATION_THREADS",
    )
    parser.add_argument(
        "--scale-factor",
        type=int,
        default=1,
        help="Warehouses per shard override (exported via MAKO_SCALE_FACTOR)",
    )
    parser.add_argument(
        "--skip-baseline",
        action="store_true",
        help="Skip the sequential baseline run",
    )
    args = parser.parse_args()

    aggregates = run_matrix(args)
    print_table(aggregates)
    print("\nAggregated logs stored in:")
    for agg in aggregates:
        print(f" - {agg.name}: {agg.log_path}")

    # Regenerate graphs from the synthetic logs (timestamped plots)
    try:
        plots_base = Path(args.log_dir) / "plots"
        subprocess.run(
            [
                sys.executable,
                "scripts/plot_batch_matrix.py",
                "--output-dir",
                str(plots_base),
            ],
            check=False,
        )
    except FileNotFoundError:
        print("[WARN] matplotlib plotting script not found; skipping graph refresh.")


if __name__ == "__main__":
    main()


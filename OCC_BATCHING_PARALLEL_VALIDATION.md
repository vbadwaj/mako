# OCC Batching & Parallel Validation

This note captures the end-to-end implementation of Sto’s OCC batch validator, how we wire up OpenMP parallel validation, plus the scripts/configs we use to benchmark, profile, and plot the results.

## Core Components

### `StoBatchValidationStats`
We track every batch lifecycle metric inside `StoBatchValidationStats`, including trigger/collection/validation timing, flush reasons, and the configured OpenMP thread count.  
```36:70:src/mako/benchmarks/sto/Transaction.cc
struct StoBatchValidationStats {
    std::atomic<uint64_t> commit_attempts{0};
    std::atomic<uint64_t> batch_requests{0};
    std::atomic<uint64_t> batches_used{0};
    std::atomic<uint64_t> num_batches{0};
    std::atomic<uint64_t> num_txns_in_batches{0};
    std::atomic<uint64_t> num_batch_committed{0};
    std::atomic<uint64_t> num_batch_aborted{0};
    std::atomic<uint64_t> total_trigger_wait_us{0};
    std::atomic<uint64_t> total_collection_wait_us{0};
    std::atomic<uint64_t> total_validation_us{0};
    std::atomic<uint64_t> flush_due_to_full{0};
    std::atomic<uint64_t> flush_due_to_timeout{0};
    std::atomic<uint64_t> max_batch_size{0};
    std::atomic<uint64_t> env_logs{0};
    bool enabled{false};
    size_t batch_size{32};
    size_t max_wait_us{1000};
    size_t validation_threads{0};
    ...
};
```

### Validator Lifecycle
`StoBatchValidator::Configure` seeds the pending batch; `Enqueue` collects transactions until either the batch fills or the timeout hits, then `ValidateBatch` fans out validation work in parallel and records stats (including the max batch size observed).  
```99:196:src/mako/benchmarks/sto/Transaction.cc
void Configure(size_t batch_size, size_t max_wait_us, size_t validation_threads) { ... }
StoBatchValidator::Result Enqueue(Transaction* txn) {
    ...
    if (trigger_validation) {
        RecordFlushTriggerStats(trigger_reason, trigger_wait_us);
        ValidateBatch(batch);
    }
    ...
    result.passed = batch->results[position];
    return result;
}
```

### Parallel Validation (OpenMP)
When `ENABLE_OPENMP` is defined we run the per-transaction validation loop inside an OpenMP `parallel for`. `MAKO_BATCH_VALIDATION_THREADS` (and `OMP_NUM_THREADS`) cap the worker pool; omitting the env var lets OpenMP pick the system default.  
```258:337:src/mako/benchmarks/sto/Transaction.cc
#if defined(ENABLE_OPENMP)
    if (validation_threads_ > 0) {
#pragma omp parallel for num_threads(validation_threads_)
        for (int64_t i = 0; i < static_cast<int64_t>(total); ++i) {
            batch->results[idx] = ValidateTransaction(batch->txns[idx]);
        }
    } else {
#pragma omp parallel for
        ...
    }
#else
    for (size_t i = 0; i < total; ++i) {
        batch->results[i] = ValidateTransaction(batch->txns[i]);
    }
#endif
...
sto_stats.total_collection_wait_us.fetch_add(collection_us, ...);
sto_stats.total_validation_us.fetch_add(validation_us, ...);
UpdateMaxBatchSize(total);
```

## Runtime Knobs

Set the following env vars per `dbtest` process (single or multi-shard):

| Env Var | Purpose |
| --- | --- |
| `MAKO_ENABLE_BATCH_VALIDATION`/`BATCH_VALIDATION` | Feature gate (set to `1`/`true`). |
| `MAKO_BATCH_VALIDATION_SIZE` | Target batch length (e.g. `16`, `32`). |
| `MAKO_BATCH_VALIDATION_MAX_WAIT_US` | Upper bound on collection wait (µs). |
| `MAKO_BATCH_VALIDATION_THREADS` | OpenMP threads for validation. Mirrors `OMP_NUM_THREADS`. |
| `MAKO_SCALE_FACTOR` | Warehouses-per-shard override. Defaults to `num_threads`, but setting this decouples offered load from worker count. |

The validator logs the active settings once per process when the first batch is initialized.

## Instrumentation

Every aggregated log (single shard or combined) now reports:

- `avg_collection_wait_us`, `avg_trigger_wait_us`, `avg_validation_time_us`
- `flush_full_count`, `flush_timeout_count`
- `max_batch_size_observed`
- `commit_attempts`, `batch_requests`, `batches_used`

We derive averages by dividing the cumulative counters above when plotting. The plotting script also converts aborts into “aborts per 1k txns” and writes all graphs into timestamped folders to avoid clobbering old runs.

## Benchmark Automation

### Single-shard sweep
Use `scripts/run_batch_matrix.py` to iterate through the baseline plus the batch configs. The script exports `MAKO_BATCH_VALIDATION_THREADS` and `OMP_NUM_THREADS`, parses the per-run log, and leaves the raw outputs under `logs/batch_matrix_*`.

### Multi-shard sweep
`scripts/run_sharded_batch_matrix.py` orchestrates N shards (default 2, we pass 3) by spawning one `dbtest` per site name, collecting each log, aggregating metrics, and calling the plotting script automatically. The run matrix includes the baseline plus four batch configs.  
```318:454:scripts/run_sharded_batch_matrix.py
runs.extend([
    RunSpec(name="batch_sz8_wait200", ...),
    RunSpec(name="batch_sz4_wait100", ...),
    RunSpec(name="batch_sz16_wait300_thr16", ...),
    RunSpec(name="batch_sz32_wait400_thr16", ...),
])
...
for idx, site_name in enumerate(sites):
    shard_log = log_dir / f"batch_matrix_{run.name}_shard{idx}.log"
    proc = run_sharded_process(..., site_name, idx, run.num_threads, env, shard_log)
    procs.append(proc)
exit_codes = [wait_process(proc) for proc in procs]
...
write_synthetic_log(aggregate, [(f"shard{idx}", shard_log) ...])
```

Invoke it like:
```
python3 scripts/run_sharded_batch_matrix.py \
  --validation-threads 12 \
  --shard-config config/local-shards3-warehouses1.yml \
  --sites s0_leader s1_leader s2_leader \
  --log-dir logs/sharded_3shards
```

### Plotting
`scripts/plot_batch_matrix.py` scans all synthetic logs, computes aborts per 1k txns (using `n_commits`), and emits plots into `logs/.../plots/<timestamp>/`. Throughput and batch-count annotations now show raw values (with comma formatting) so we no longer see “0” on the charts.

## Multi-shard Config

We keep a 3-shard localhost layout in `config/local-shards3-warehouses1.yml` so we can run 2–3 concurrent validator instances without port conflicts.  
```1:24:config/local-shards3-warehouses1.yml
sites:
  - name: "s0_leader" ... port: 31013
  - name: "s1_leader" ... port: 31015
  - name: "s2_leader" ... port: 31017
shard_map:
  - ["s0_leader"]
  - ["s1_leader"]
  - ["s2_leader"]
warehouses: 1
memlocalhost: 31500
```

## Operational Notes

1. **CPU sizing:** On 32 vCPUs we run 16 worker threads per shard to stay under the 200-table allocator limit. If you need more load, raise the per-shard warehouse count or bump the table cap inside the allocator.
2. **Timeout tuning:** When `flush_timeout_count` dwarfs `flush_full_count`, lower `MAKO_BATCH_VALIDATION_MAX_WAIT_US` (e.g. 300 → 200 µs) before increasing batch size.
3. **Validation threads:** Start with `validation_threads = min(batch_size, available_cores/2)` and adjust if `avg_validation_time_us` begins to dominate the total batch latency.
4. **Graph hygiene:** Every sweep creates a unique folder under `logs/sharded_*/plots/` so we can diff historical runs. Record the timestamp printed at the end of the script.

With these pieces you can enable batching, control the OpenMP fan-out, profile where the batch validator spends its time, and visualize the effect across single- and multi-shard deployments without manual log munging.

## From Baseline OCC to Multi-Shard Parallel Validation

1. **Baseline OCC bring-up**  
   - Verified sequential OCC (`MAKO_ENABLE_BATCH_VALIDATION=0`) using `scripts/run_batch_matrix.py` to capture throughput/latency references.  
   - Ensured `dbtest` was launched via `--shard-config` (new format parser at `configuration.cc:99`) instead of the legacy `--config/--warehouses` flags.

2. **Batching feature flag + stats**  
   - Introduced `StoBatchValidationStats` and `configure_batch_validation_from_env()` so `MAKO_ENABLE_BATCH_VALIDATION`, `MAKO_BATCH_VALIDATION_SIZE`, and `MAKO_BATCH_VALIDATION_MAX_WAIT_US` can be toggled at runtime.  
   - Added per-batch timing hooks (`opened_at`, `sealed_at`) and flush reasons to understand starvation vs. full flushes.

3. **OpenMP parallel validation**  
   - Wrapped the validation loop in `#pragma omp parallel for` (guarded by `ENABLE_OPENMP`) and exposed `MAKO_BATCH_VALIDATION_THREADS` so operators can pin the thread count per shard.  
   - Mirrored the setting into both the STO stats and the global benchmark output for later plotting.

4. **Profiling + plotting overhaul**  
   - Extended `scripts/run_batch_matrix.py` to pass the new env vars, parse the richer metrics, and feed them into `scripts/plot_batch_matrix.py`.  
   - Updated the plotting script to compute “aborts per 1k txns,” annotate throughput/batch counts with raw numbers, and emit every run into a timestamped folder to preserve history.

5. **Multi-shard automation**  
   - Authored `scripts/run_sharded_batch_matrix.py` to spawn a `dbtest` process per site, wait for all shards, merge their stats, and regenerate plots automatically.  
   - Created `config/local-shards3-warehouses1.yml` so we can safely run three local leaders on ports 31013/31015/31017 without RPC conflicts.

6. **High-load experimentation**  
   - Scaled to a 32 vCPU box, tuned per-shard worker threads (capped at 16 to stay within the table-id limit), and experimented with `batch_sz16_wait300` vs. `batch_sz32_wait400`.  
   - Observed that `flush_timeout_count` dominates, informing the next round of heuristics (shorter waits or more offered load).

7. **Documentation & hand-off**  
   - Captured the full flow—including env knobs, validation details, automation scripts, and operational guidance—in this Markdown so future runs or regressions can be traced quickly.

## High-Load Tuning (Dec 2025)

- **Scale-factor override:** `dbtest` now reads `MAKO_SCALE_FACTOR` right after CLI parsing so we can keep 24 client threads but only 3–6 warehouses per shard.  
```158:164:src/mako/benchmarks/dbtest.cc
  // Optional override: allow MAKO_SCALE_FACTOR to decouple warehouses-per-shard from thread count
  if (const char* scale_env = std::getenv("MAKO_SCALE_FACTOR")) {
    double scale_override = std::strtod(scale_env, nullptr);
    if (scale_override > 0) {
      benchConfig.setScaleFactor(scale_override);
    }
  }
```
- **Multi-shard script wiring:** `scripts/run_sharded_batch_matrix.py` now accepts `--scale-factor` and exports `MAKO_SCALE_FACTOR` per `RunSpec`, alongside per-run OpenMP overrides.
- **Helper-ID constraint:** Dropping the scale factor below ~3 causes every process to panic with `Invalid shardIdx:5`. The STO control threads reserve extra logical IDs (`warehouses+1` through `warehouses+4`), so shrinking `warehouses` collapses those IDs onto nonexistent shards.  
```275:333:src/mako/benchmarks/sto/sync_util.hh
// erpc ports:
//   0-warehouses-1: db worker threads
//   warehouses+1: exchange watermark server
//   warehouses+2: exchange watermark client
//   warehouses+3: control client
auto id = config->warehouses + 4;
...
control_sclient->remoteControl(control, value, ret_value, dstShardIndex);
```
- **Resulting limitation:** The current helper numbering requires `warehouses >= 6` to keep all reserved IDs within `nshards * warehouses`. Attempts with `MAKO_SCALE_FACTOR=1` or `3` hit `rrr_rpc_backend.cc:243` panics (`logs/sharded_3shards_tuned/batch_matrix_baseline_shard*.log`). Until we refactor the helper ID scheme, the minimum safe scale factor on a 3-shard deployment is the default (number of client threads divided by shards).

## Single-Shard Benchmark Summary (Dec 2025)

### Experimental Methodology
- **Workload & dataset**  
  - TPCC transaction mix `[45, 43, 4, 4, 4]`, local in-memory deployment via `config/local-tpcc-baseline.yml` (single shard, Masstree tables).
  - Each run starts from a cold load to avoid reuse of warmed caches/logs.
- **Hardware configuration**  
  - c6i.8xlarge-equivalent host (32 vCPUs, 64 GiB RAM).  
  - jemalloc configured with 2 MB huge pages; NUMA binding left to the OS.  
  - No disk persistence (RocksDB disabled) to isolate OCC/batching behavior.
- **Execution protocol**  
  1. Invoke `scripts/run_batch_matrix.py` with the desired OpenMP cap (e.g., `--validation-threads 6`) and `--log-dir logs/<tag>`.  
  2. For each RunSpec, the script prints the exact `dbtest` command, captures stdout/stderr into `logs/<tag>/batch_matrix_<name>.log`, and flags non-zero exit codes.  
  3. After the sweep, `scripts/plot_batch_matrix.py` is run to produce a timestamped figure bundle.
- **Measured quantities**  
  - **Throughput & latency:** `agg_throughput`, `avg_latency` fields inside each log.  
  - **Abort cost:** `agg_abort_rate` plus derived “aborts per 1k txns” metric.  
  - **Batch health:** `avg_collection_wait_us`, `avg_validation_time_us`, `flush_full_count`, `flush_timeout_count`, `max_batch_size_observed`.  
  - **Validation parallelism:** `validation_threads` confirms the number of OpenMP workers actually used.
- **Interpretation rubric**  
  - If `avg_collection_wait_us` ≫ `avg_validation_time_us`, throughput is limited by queue starvation.  
  - If `flush_timeout_count` ≫ `flush_full_count`, the batch never fills before the wait cap, so reducing `MAKO_BATCH_VALIDATION_MAX_WAIT_US` or increasing load should be prioritized.  
  - Improvements are only meaningful if `agg_throughput` × (1 − abort%) exceeds the baseline’s committed throughput (~615 k ops/s).

### End-to-End Workflow (What we actually did)
1. **Instrumentation overhaul**: Added OpenMP hooks, STO stats, and richer logging to `StoBatchValidator`, then wired those metrics into both `run_batch_matrix.py` and `plot_batch_matrix.py`.
2. **Baseline validation**: Verified the sequential OCC baseline (8 workers) to establish the reference throughput/latency envelope and to ensure the new logging format works.
3. **Batch parameter sweeps** (single shard):
   - Batch size 8 / wait 200 µs, validation threads 6 (`logs/single_shard_tuned_bs8_wait100/.../batch_sz8_wait200.log`).
   - Batch size 4 / wait 100 µs (`.../batch_sz4_wait100.log`).
   - Batch size 16 / wait 500 µs, 16 workers (`.../batch_sz16_wait500_thr16.log`).
   - Alternate 16-thread run with wait 200 µs (`logs/single_shard_tuned/manual_batch_sz16_wait200_thr16.log`).
4. **Plotting & reporting**: Generated timestamped figure bundles (e.g., `logs/single_shard_tuned_bs8_wait100/plots/20251203-044859/`) and summarized the findings in this document.
5. **High-load prep**: Raised `NUM_TABLES_PER_SHARD` to 512, added optional `MAKO_SCALE_FACTOR`, and attempted multi-shard sweeps via `scripts/run_sharded_batch_matrix.py` (documented under “High-Load Tuning”).
6. **Troubleshooting**: Identified helper-ID constraints (ERPC transport IDs rely on `warehouses+1..+4`), `perf` profiling limitations (`perf_event_paranoid=4`), and queue starvation root causes (timeouts dominating flush counts).
7. **Documentation**: Consolidated all methodologies, commands, and observations here so future experiments can be reproduced.

### Baseline (sequential OCC)
- Command: `./build/dbtest --site-name local_s0 --shard-config config/local-tpcc-baseline.yml --num-threads 8`
- Throughput `≈ 615k ops/s`, latency `≈ 0.012 ms`, abort rate `≈ 109/s`
- Log: `logs/single_shard_tuned_bs8_wait100/batch_matrix_baseline.log`

### Batch size 8, wait 200µs, 6 validation threads
```
OMP_NUM_THREADS=6 MAKO_BATCH_VALIDATION_THREADS=6 \
MAKO_ENABLE_BATCH_VALIDATION=1 BATCH_VALIDATION=1 \
MAKO_BATCH_VALIDATION_SIZE=8 MAKO_BATCH_VALIDATION_MAX_WAIT_US=200 \
./build/dbtest --site-name local_s0 \
  --shard-config config/local-tpcc-baseline.yml --num-threads 8
```
- Throughput `≈ 100k ops/s`, `avg_collection_wait_us ≈ 125`, `avg_validation_time_us ≈ 2`, `flush_full_count 378k`, `flush_timeout_count 240k`
- Log: `logs/single_shard_tuned_bs8_wait100/batch_matrix_batch_sz8_wait200.log`
  - **Interpretation:** Even after lowering the OpenMP cap to 6 threads, the collection queue still dictates performance (125 µs vs. 2 µs). However, the `flush_full` to `flush_timeout` ratio improved to ~1.6:1, proving that shaving wait time directly increases throughput. Further improvements require either more offered load or shorter waits.

### Batch size 4, wait 100µs
```
... MAKO_BATCH_VALIDATION_SIZE=4 MAKO_BATCH_VALIDATION_MAX_WAIT_US=100 ...
```
- Throughput `≈ 172k ops/s`, `avg_collection_wait_us ≈ 32`, `flush_full_count 1.1M`, `flush_timeout_count 0.4M`
- Log: `.../batch_matrix_batch_sz4_wait100.log`
  - **Interpretation:** The queue finally spends most of its time collecting for only a few dozen microseconds. Almost every batch hits capacity, so batching adds minimal latency. Despite that, throughput remains <30 % of baseline because the batch-size reduction also limits parallelism. This configuration is useful as a “low-latency” batch mode but still needs more load to exceed the baseline throughput.

### Batch size 16, wait 500µs, 16 threads
```
OMP_NUM_THREADS=6 MAKO_BATCH_VALIDATION_THREADS=6 \
MAKO_BATCH_VALIDATION_SIZE=16 MAKO_BATCH_VALIDATION_MAX_WAIT_US=500 \
./build/dbtest --site-name local_s0 --num-threads 16 ...
```
- Throughput `≈ 110k ops/s`, `avg_collection_wait_us ≈ 407`, `avg_validation_time_us ≈ 3`, `flush_full_count 208k`, `flush_timeout_count 480k`
- Log: `.../batch_matrix_batch_sz16_wait500_thr16.log`
  - **Interpretation:** Despite 16 worker threads, the collector remains idle for ~0.4 ms per batch and half the flushes still trigger on timeout. Without raising offered load (more client threads or warehouses) this setting will never beat baseline; all of the available CPU is waiting on the batch barrier rather than validating.

### Alternate 16-thread run (wait 200µs)
```
OMP_NUM_THREADS=8 MAKO_BATCH_VALIDATION_THREADS=8 \
MAKO_BATCH_VALIDATION_SIZE=16 MAKO_BATCH_VALIDATION_MAX_WAIT_US=200 \
./build/dbtest --site-name local_s0 --num-threads 16 ...
```
- Throughput `≈ 117k ops/s`, `avg_collection_wait_us ≈ 197`, `avg_validation_time_us ≈ 3`, `flush_full_count 219,906`, `flush_timeout_count 480,322`
- Log: `logs/single_shard_tuned/manual_batch_sz16_wait200_thr16.log`
  - **Interpretation:** Shrinking the wait cap halves the idle time, but timeouts still outnumber full flushes 2:1, so the run is still collection-bound. Adaptive waits (e.g., shorten when the queue is empty) or higher offered load are required to move this configuration past the baseline throughput.

### Plots
- Timestamped figures for the latest single-shard sweep: `logs/single_shard_tuned_bs8_wait100/plots/20251203-044859/`
- Summary includes throughput, latency, abort-per-1k, and batch stats panels.

## ELI5 Recap

- Think of each shard as a grocery clerk checking receipts (transactions). Instead of checking one at a time, we wait until a small pile (the batch) shows up.
- We give the clerks a maximum wait timer so they don’t stare at an empty counter forever; when the buzzer goes off, they check whatever is in the pile.
- When the pile is ready, we invite extra clerks (OpenMP threads) to check each receipt in parallel so the queue clears faster.
- We keep a scoreboard that notes how long we waited, how many receipts passed/failed, and why we flushed the pile (full vs timeout).
- After each experiment we draw charts every time, saving them with timestamps so we can compare today’s grocery rush to yesterday’s.



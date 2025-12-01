# Batch Validation Profiling Guide

This guide explains how to profile batch validation performance to identify bottlenecks.

## Overview

The profiling infrastructure measures:
1. **Overall Performance**: Throughput, latency, abort rates
2. **Performance Counters**: Time spent in each commit phase
3. **Batch Validation Overhead**: Mutex wait, batch collection, parallel validation time

## Quick Start

### 1. Build with Performance Counters

Ensure Mako is built with performance profiling enabled:

```bash
cd build
cmake .. -DUSE_PERF_CTRS=ON -DENABLE_BATCH_VALIDATION=ON -DENABLE_OPENMP=ON
make -j$(nproc)
```

### 2. Run Profiling

```bash
./profile_batch_validation.sh
```

This will:
- Run baseline test (no batch validation)
- Run with batch validation (size=32)
- Run with batch validation (size=64)
- Save results to `results/profile_validation/`

### 3. Analyze Results

```bash
python3 scripts/analyze_profile_results.py results/profile_validation
```

## What Gets Measured

### Throughput Metrics
- **txns_per_second**: Total transaction throughput
- **committed**: Number of committed transactions
- **abort_rate**: Abort rate (aborts/sec)
- **avg_latency_ms**: Average transaction latency

### Performance Counters (microseconds)
- **total_commit_time_us**: Total time spent in commit()
- **validation_time_us**: Time spent in validation phase
- **read_validation_time_us**: Time validating read set
- **absent_validation_time_us**: Time validating absent set (btree versions)

### Batch Validation Overhead (microseconds)
- **avg_mutex_wait_us**: Time waiting to acquire batch mutex
- **avg_batch_wait_us**: Time waiting for batch to fill/timeout
- **avg_collection_time_us**: Total time in batch collection (mutex + wait)
- **avg_batch_validation_time_us**: Time spent in parallel validation
- **avg_batch_size**: Average number of transactions per batch

## Interpreting Results

### If Validation Time is Small (< 20% of total commit time)

**Batch validation won't help much!** The bottleneck is elsewhere:
- Network RPCs (cross-shard transactions)
- Lock acquisition
- Write installation
- Other coordination overhead

### If Mutex Wait Time is High

The single mutex is a bottleneck. Solutions:
- Use per-core batch queues (like Mako's per-core Paxos streams)
- Use lock-free batch collection
- Reduce batch size to reduce contention

### If Batch Wait Time is High

Transactions are waiting too long for batches to fill. Solutions:
- Reduce batch size
- Reduce max wait time
- Use adaptive batching based on load

### If Validation Time is High (> 40% of total commit time)

Batch validation should help! But check:
- Is OpenMP enabled? (`#ifdef _OPENMP`)
- Are enough cores available?
- Is the validation actually parallelizing?

## Example Output

```
=== Batch Validation Profiling Results ===
--- Throughput Comparison ---
Metric                          Baseline            Batch=32            Batch=64            
--------------------------------------------------------------------------------
Throughput (txns/sec)           125000.00           124500.00           124000.00           
Committed Transactions          3750000              3735000              3720000           
Abort Rate                      50.00               52.00               53.00              
Avg Latency (ms)                2.50                2.55                2.60               

Speedup vs Baseline: Batch=32: -0.40%, Batch=64: -0.80%

--- Performance Counter Breakdown (microseconds) ---
Phase                           Baseline            Batch=32            Batch=64            
--------------------------------------------------------------------------------
Total Commit Time               10.00               10.50               11.00              
Validation Time                 1.50                1.20                1.10               
Read Validation                 1.20                0.95                0.90               
Absent Validation               0.30                0.25                0.20               

--- Batch Validation Overhead (Batch=32) ---
Batch Validations: 116875
Validated Transactions: 3735000
Aborted Transactions: 50000
Avg Batch Size: 31.95
Avg Batch Validation Time (us): 0.80
Avg Mutex Wait Time (us): 2.30
Avg Batch Wait Time (us): 0.50
Avg Collection Time (us): 2.80

Total Batch Overhead: 2.80 us
Overhead as % of Validation Time: 233.33%

--- Bottleneck Analysis ---
Validation time: 15.00% of total commit time
  - Read validation: 12.00%
  - Absent validation: 3.00%

⚠️  WARNING: Validation is < 20% of total commit time!
   Batch validation may not help much - the bottleneck is elsewhere.
```

## Troubleshooting

### Performance counters show 0

1. Check if `USE_PERF_CTRS` is enabled in CMake
2. Ensure `MAKO_ENABLE_PERFORMANCE_PROFILING=1` environment variable is set
3. Check that the probes are registered (look for `scopedperf` output in logs)

### Batch validation metrics show 0

1. Verify batch validation is enabled: `export MAKO_ENABLE_BATCH_VALIDATION=1`
2. Check that transactions are actually using batch validation (not all are snapshots)
3. Look for batch validation statistics in the log output

### No speedup with batch validation

Possible reasons:
- Validation time is already small (< 20% of commit time)
- Mutex contention is too high
- Not enough cores for parallelization
- OpenMP not enabled
- Overhead outweighs benefits for fast transactions





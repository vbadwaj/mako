# Baseline Performance Profiling Plan

## Goal
Measure baseline performance across different core counts (1, 2, 4, 8) and profile time spent in different parts of the transaction protocol to establish a baseline before comparing with parallel batch validation.

## What We Need to Measure

### 1. **Overall Metrics** (per core count)
- **Throughput**: Transactions per second (TPS)
- **Latency**: Average commit time per transaction
- **Abort Rate**: Percentage of transactions that abort

### 2. **Protocol Phase Breakdown** (time spent in each phase)
Based on existing probes in `txn_impl.h`:
- **probe0**: Total commit time
- **probe1**: Copy write tuples to vector
- **probe2**: Lock write nodes
- **probe3**: Read validation (OCC version checking) ← **KEY PHASE**
- **probe4**: Write records (install writes)
- **probe5**: Generate commit TID
- **probe6**: Sort write nodes

### 3. **Additional Metrics We Should Track**
- **Read set size**: Average number of tuples read
- **Write set size**: Average number of tuples written
- **Validation iterations**: How many version checks performed
- **Lock acquisition time**: Time spent acquiring locks
- **Abort reasons**: Breakdown by abort type

## Implementation Approach

### Phase 1: Enhance Existing Performance Instrumentation

Mako already has performance probes using `ANON_REGION` and TSC counters. We need to:

1. **Add more granular probes** in key sections:
   - Time spent in read set validation loop
   - Time spent in absent set validation
   - Time spent in batch validation (if enabled)
   - Lock contention time (spin-wait time)

2. **Add event counters** for statistics:
   - Read set sizes (average)
   - Write set sizes (average)
   - Abort reasons (count per type)

3. **Create a performance profiler class** similar to existing infrastructure:
   - Collect per-transaction timing data
   - Aggregate across threads
   - Export in structured format (JSON/CSV)

### Phase 2: Core Pinning Infrastructure

Create a test harness that:
- Pins threads to specific CPU cores
- Tests with 1, 2, 4, 8 cores
- Uses `pthread_setaffinity_np` or cgroups
- Ensures clean core isolation

### Phase 3: Test Benchmark

Create a benchmark that:
- Uses a controlled workload (e.g., TPC-C or synthetic)
- Runs for a fixed duration (e.g., 30 seconds)
- Collects performance data during run
- Outputs results in parseable format

### Phase 4: Data Collection and Analysis

- Aggregate performance counters
- Calculate phase breakdowns (percentage of time)
- Generate reports comparing different core counts
- Visualize results (optional)

## Existing Infrastructure to Leverage

### 1. Performance Probes (`scopedperf.hh`)
```cpp
ANON_REGION("region_name", &counter_group);
```
Already used in commit path.

### 2. Event Counters (`counter.h`)
```cpp
static event_counter g_counter;
g_counter.inc();
```
Already used for abort reasons.

### 3. Thread Affinity
Mako has examples of thread pinning:
- `src/mako/vec/occ.cpp` uses `pthread_setaffinity_np`
- `bash/shard.sh` uses cgroups

## Implementation Details

### A. Enhanced Performance Probes

Add new probes in `txn_impl.h`:

```cpp
// In read validation section
PERF_DECL(
    static std::string probe_read_validation_loop_name(
      std::string(__PRETTY_FUNCTION__) + std::string(":read_validation_loop:")));
ANON_REGION(probe_read_validation_loop_name.c_str(), 
            &transaction_base::g_txn_read_validation_loop_cg);

// In absent set validation
PERF_DECL(
    static std::string probe_absent_validation_name(
      std::string(__PRETTY_FUNCTION__) + std::string(":absent_validation:")));
ANON_REGION(probe_absent_validation_name.c_str(), 
            &transaction_base::g_txn_absent_validation_cg);
```

### B. Performance Data Collector

Create a new class `PerformanceCollector`:

```cpp
class PerformanceCollector {
public:
  struct PhaseTiming {
    uint64_t total_cycles;
    uint64_t count;
    double avg_us() const { return cycles_to_us(total_cycles) / count; }
  };
  
  struct TransactionStats {
    PhaseTiming total_commit;
    PhaseTiming lock_write_nodes;
    PhaseTiming read_validation;
    PhaseTiming write_records;
    // ...
    size_t read_set_size;
    size_t write_set_size;
    bool aborted;
  };
  
  void record_transaction(const TransactionStats& stats);
  void aggregate_results();
  void print_report(int num_cores);
  void export_csv(const std::string& filename, int num_cores);
};
```

### C. Core-Pinning Test Script

Create a script that:
1. Sets CPU affinity using `taskset` or cgroups
2. Runs benchmark with different core counts
3. Collects output and parses results

```bash
#!/bin/bash
# test_baseline_performance.sh

for cores in 1 2 4 8; do
  echo "Testing with $cores cores..."
  
  # Pin to first N cores
  taskset -c 0-$((cores-1)) \
    ./build/dbtest \
    --num-threads $cores \
    --bench tpcc \
    --duration 30 \
    --enable-performance-profiling \
    > results/baseline_${cores}cores.log 2>&1
  
  # Parse and extract metrics
  python3 scripts/parse_baseline_results.py \
    results/baseline_${cores}cores.log \
    > results/baseline_${cores}cores.json
done
```

### D. Results Format

Generate structured output:

```json
{
  "core_count": 4,
  "duration_seconds": 30,
  "throughput": {
    "total_txns": 1500000,
    "txns_per_second": 50000,
    "committed": 1425000,
    "aborted": 75000,
    "abort_rate": 0.05
  },
  "latency": {
    "avg_commit_us": 20.5,
    "p50_commit_us": 18.2,
    "p95_commit_us": 35.7,
    "p99_commit_us": 52.3
  },
  "phase_breakdown": {
    "total_commit": {"avg_us": 20.5, "pct": 100.0},
    "copy_write_tuples": {"avg_us": 0.3, "pct": 1.5},
    "lock_write_nodes": {"avg_us": 2.1, "pct": 10.2},
    "read_validation": {"avg_us": 12.5, "pct": 61.0},
    "write_records": {"avg_us": 4.8, "pct": 23.4},
    "gen_commit_tid": {"avg_us": 0.8, "pct": 3.9}
  },
  "transaction_stats": {
    "avg_read_set_size": 5.2,
    "avg_write_set_size": 2.3,
    "avg_absent_set_size": 1.1
  }
}
```

## Testing Strategy

### Test Configuration
- **Workload**: TPC-C or synthetic key-value workload
- **Duration**: 30 seconds per test
- **Core counts**: 1, 2, 4, 8
- **Threads per core**: 1 (to avoid hyperthreading effects initially)
- **Batch validation**: **DISABLED** (this is baseline)

### Test Execution Order
1. Run with 1 core, collect data
2. Run with 2 cores, collect data
3. Run with 4 cores, collect data
4. Run with 8 cores, collect data
5. Aggregate and compare results

### Expected Results
- **Throughput scaling**: Should scale roughly linearly up to a point
- **Validation time**: Should be a significant portion of commit time
- **Validation bottleneck**: Should become more apparent with more cores

## Files to Create/Modify

### New Files
1. `src/mako/performance_collector.h` / `.cc` - Performance data collection
2. `scripts/run_baseline_performance.sh` - Test execution script
3. `scripts/parse_baseline_results.py` - Results parsing
4. `scripts/compare_baseline_results.py` - Comparison and visualization
5. `tests/baseline_performance_test.cc` - Benchmark test

### Modified Files
1. `src/mako/txn_impl.h` - Add additional performance probes
2. `src/mako/txn.h` - Add new probe counter declarations
3. `src/mako/txn.cc` - Implement new probe counters
4. `src/mako/benchmarks/bench.cc` - Integrate performance collector
5. `CMakeLists.txt` - Add performance profiling options

## Deliverables

1. **Performance Profiler**: Enhanced instrumentation in commit path
2. **Test Scripts**: Automated testing across core counts
3. **Results**: CSV/JSON files with detailed breakdowns
4. **Report**: Document showing baseline performance characteristics
5. **Visualizations**: Charts showing phase breakdown by core count

## Next Steps (Implementation Order)

1. **Add granular performance probes** to commit path
2. **Create PerformanceCollector class** for data aggregation
3. **Build test benchmark** with core pinning
4. **Run baseline tests** across core counts
5. **Analyze results** and document findings

## Questions to Answer

1. How does throughput scale with core count?
2. What percentage of commit time is spent in validation?
3. Does validation become a bottleneck at higher core counts?
4. What is the abort rate at different core counts?
5. How do read/write set sizes affect performance?

This baseline will then allow us to compare against parallel batch validation to quantify improvements.

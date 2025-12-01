# Baseline Performance Testing Guide

## Overview

This guide explains how to run baseline performance tests using TPC-C across different core counts to establish performance profiles before comparing with parallel batch validation.

## Quick Start

### 1. Build Mako

Make sure Mako is built with performance profiling enabled:

```bash
cd build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
make -j
```

### 2. Run Baseline Tests

Run the baseline performance test script:

```bash
./test_baseline_performance_tpcc.sh
```

This will:
- Test with 1, 2, 4, and 8 cores
- Pin threads to specific cores using `taskset`
- Disable batch validation (baseline)
- Run for 30 seconds per configuration
- Save results to `results/baseline_performance/`

### 3. Parse Results

Parse and analyze the results:

```bash
python3 scripts/parse_baseline_results.py results/baseline_performance
```

## What Gets Measured

### Overall Metrics
- **Throughput**: Transactions per second
- **Commit/Abort counts**: Total committed and aborted transactions
- **Abort rate**: Percentage of transactions that abort

### Protocol Phase Breakdown

The enhanced performance probes measure time spent in:

1. **probe0**: Total commit time
2. **probe1**: Copy write tuples to vector
3. **probe2**: Lock write nodes
4. **probe3**: Total read validation (OCC version checking)
5. **probe4**: Write records (install writes)
6. **probe5**: Generate commit TID
7. **probe6**: Sort write nodes
8. **read_set_validation**: Time in read set validation loop
9. **absent_set_validation**: Time in absent set validation

## Test Configuration

### Core Counts Tested
- 1 core
- 2 cores
- 4 cores
- 8 cores

### Test Parameters
- **Duration**: 30 seconds per test
- **Workload**: TPC-C
- **Scale factor**: Matches thread count
- **Batch validation**: Disabled (baseline)

### Core Pinning
Threads are pinned to cores using `taskset`:
- 1 core: core 0
- 2 cores: cores 0-1
- 4 cores: cores 0-3
- 8 cores: cores 0-7

## Output Files

After running tests, you'll find:

```
results/baseline_performance/
├── baseline_1cores.log     # Detailed log for 1 core
├── baseline_1cores.json    # Summary JSON for 1 core
├── baseline_2cores.log
├── baseline_2cores.json
├── baseline_4cores.log
├── baseline_4cores.json
├── baseline_8cores.log
├── baseline_8cores.json
└── summary.json            # Combined summary (after parsing)
```

## Manual Testing

If you want to run a single test manually:

```bash
# Test with 4 cores
taskset -c 0-3 \
  ./build/benchmarks/dbtest \
  --bench tpcc \
  --num-threads 4 \
  --scale-factor 4 \
  --shard-config config/local-shards2-warehouses1.yml \
  --shard-index 0 \
  --runtime 30
```

## Customizing Tests

Edit `test_baseline_performance_tpcc.sh` to change:

- **Core counts**: Modify `CORE_COUNTS=(1 2 4 8)`
- **Duration**: Change `DURATION=30`
- **Config file**: Change `CONFIG_FILE`

## Accessing Performance Counters

The performance counters can be accessed programmatically:

```cpp
// In your code or benchmark
auto counters = event_counter::get_all_counters();
for (const auto &p : counters) {
    std::cout << p.first << ": " << p.second << std::endl;
}
```

## Understanding Results

### Throughput Scaling
- Should scale roughly linearly with core count (up to a point)
- Memory bandwidth may become a bottleneck at higher core counts

### Validation Time
- **Read validation (probe3)** should be a significant portion of commit time
- This is where parallel batch validation will show improvement

### Phase Breakdown
Look for:
- **Validation overhead**: Time spent in probe3 (read validation)
- **Lock contention**: Time in probe2 (lock write nodes)
- **Write overhead**: Time in probe4 (write records)

## Troubleshooting

### Binary Not Found
```
ERROR: Binary not found at build/benchmarks/dbtest
```
**Solution**: Build Mako first:
```bash
cd build && cmake .. && make -j
```

### Config File Not Found
```
ERROR: Config file not found: config/local-shards2-warehouses1.yml
```
**Solution**: Make sure you're running from the Mako root directory.

### Permission Denied (taskset)
If you get permission errors with taskset, you may need to:
- Run with appropriate permissions
- Or modify the script to not use taskset (remove core pinning)

### No Performance Counters
If performance counters aren't showing up:
- Make sure Mako was built with `ENABLE_EVENT_COUNTERS`
- Check that the benchmark actually ran (check log files)

## Next Steps

After establishing baseline:
1. Compare with parallel batch validation enabled
2. Analyze which phases benefit most from parallelization
3. Tune batch size and validation parameters
4. Document improvements

## References

- `HOW_OCC_IS_IMPLEMENTED.md`: How OCC validation works
- `BASELINE_PERFORMANCE_PLAN.md`: Detailed plan
- `WORKLOAD_COMPARISON.md`: TPC-C vs synthetic workloads



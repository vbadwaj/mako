# ✅ Baseline Performance Testing - Setup Complete

## What's Been Created

### 1. Enhanced Performance Probes ✅
- **Added granular probes** in `src/mako/txn_impl.h`:
  - `g_txn_read_set_validation`: Time in read set validation loop
  - `g_txn_absent_set_validation`: Time in absent set validation
- **Existing probes** already measure:
  - Total commit time (probe0)
  - Copy write tuples (probe1)
  - Lock write nodes (probe2)
  - Total read validation (probe3)
  - Write records (probe4)
  - Generate commit TID (probe5)
  - Sort write nodes (probe6)

### 2. TPC-C Baseline Test Script ✅
- **File**: `test_baseline_performance_tpcc.sh`
- **Features**:
  - Tests with 1, 2, 4, 8 cores
  - Core pinning using `taskset`
  - Automatic result collection
  - JSON output for each configuration

### 3. Results Parser ✅
- **File**: `scripts/parse_baseline_results.py`
- **Features**:
  - Parses log files and extracts metrics
  - Calculates phase breakdowns
  - Generates summary tables
  - Exports JSON summary

### 4. Documentation ✅
- **File**: `BASELINE_PERFORMANCE_TESTING.md`
  - Complete guide on how to run tests
  - Explanation of what gets measured
  - Troubleshooting tips

## Quick Start

### Step 1: Build Mako
```bash
cd build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
make -j
cd ..
```

### Step 2: Run Baseline Tests
```bash
./test_baseline_performance_tpcc.sh
```

This will:
- Run TPC-C with 1, 2, 4, 8 cores
- Pin threads to specific cores
- Disable batch validation (baseline)
- Save results to `results/baseline_performance/`

### Step 3: Parse Results
```bash
python3 scripts/parse_baseline_results.py results/baseline_performance
```

## What You'll Get

### For Each Core Count (1, 2, 4, 8):
- Throughput (txns/sec)
- Commit/abort counts
- Abort rate
- Protocol phase breakdown (time spent in each phase)

### Phase Breakdown Includes:
1. Total commit time
2. Copy write tuples
3. Lock write nodes
4. **Read validation** (this is the key one!)
5. Write records
6. Generate commit TID
7. Sort write nodes
8. Read set validation (detailed)
9. Absent set validation (detailed)

## Expected Output

After running, you'll see:
```
results/baseline_performance/
├── baseline_1cores.log
├── baseline_1cores.json
├── baseline_2cores.log
├── baseline_2cores.json
├── baseline_4cores.log
├── baseline_4cores.json
├── baseline_8cores.log
├── baseline_8cores.json
└── summary.json
```

## Next Steps

1. **Run baseline tests** to establish performance profile
2. **Analyze results** to see where time is spent
3. **Compare with parallel batch validation** when enabled
4. **Document improvements** in performance breakdown

## Notes

- Tests run for **30 seconds** per configuration (configurable)
- Uses **TPC-C** workload for realism
- Core pinning ensures clean isolation
- Results are automatically collected and parsed

## Questions?

See `BASELINE_PERFORMANCE_TESTING.md` for detailed documentation.



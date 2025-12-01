# 📊 Complete Benchmarking Guide for Mako

## Table of Contents
1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Building Mako](#building-mako)
4. [Understanding the Benchmark Setup](#understanding-the-benchmark-setup)
5. [Running Baseline Tests](#running-baseline-tests)
6. [Running Parallel Batch Validation Tests](#running-parallel-batch-validation-tests)
7. [Comparing Results](#comparing-results)
8. [Understanding the Results](#understanding-the-results)
9. [Customization Options](#customization-options)
10. [Troubleshooting](#troubleshooting)
11. [Advanced Usage](#advanced-usage)

---

## Overview

This guide covers benchmarking Mako's transaction processing performance using TPC-C workload. You'll learn how to:

- **Baseline Testing**: Measure standard sequential validation performance
- **Parallel Testing**: Measure parallel batch validation performance
- **Comparison**: Analyze differences between baseline and parallel approaches
- **Visualization**: Generate charts and reports

### What Gets Measured

- **Throughput**: Transactions per second (txns/s)
- **Latency**: Average transaction latency (ms)
- **Abort Rate**: Percentage of transactions that abort
- **Scaling Efficiency**: How well performance scales with core count
- **Per-Core Performance**: Throughput per core (efficiency metric)

---

## Prerequisites

### System Requirements

- Linux system with multiple CPU cores (recommended: 4+ cores)
- CMake 3.10+
- C++ compiler with C++17 support (GCC 7+ or Clang 5+)
- Python 3.6+ with pandas, matplotlib, seaborn, numpy
- OpenMP library (for parallel batch validation)

### Check Your System

```bash
# Check CPU cores
nproc
lscpu

# Check Python
python3 --version

# Check Python packages
python3 -c "import pandas, matplotlib, seaborn, numpy; print('All packages available')"

# Check OpenMP
gcc -fopenmp --version
```

### Install Missing Dependencies

```bash
# Python packages
pip3 install pandas matplotlib seaborn numpy

# OpenMP (if needed)
sudo apt-get install libomp-dev  # Ubuntu/Debian
# or
sudo yum install libgomp        # CentOS/RHEL
```

---

## Building Mako

### Step 1: Navigate to Build Directory

```bash
cd /home/ubuntu/mako/build
```

### Step 2: Configure CMake

#### For Baseline Tests (Sequential Validation)

```bash
cmake .. -DENABLE_BATCH_VALIDATION=OFF
```

#### For Parallel Batch Validation Tests

```bash
cmake .. -DENABLE_BATCH_VALIDATION=ON -DENABLE_OPENMP=ON
```

**Note**: You can build with both configurations, but you'll need separate builds or rebuild between test types.

### Step 3: Build

```bash
make -j$(nproc)
```

This compiles Mako using all available CPU cores for faster compilation.

### Step 4: Verify Build

```bash
# Check if dbtest binary exists
ls -lh build/dbtest
# or
ls -lh build/benchmarks/dbtest

# Test that it runs
./build/dbtest --help
```

### Quick Build Script

You can also use the automated build script:

```bash
./build_progressive.sh
```

---

## Understanding the Benchmark Setup

### Test Configuration

The benchmarking scripts use the following default settings:

- **Workload**: TPC-C (Transaction Processing Performance Council Benchmark C)
- **Duration**: 30 seconds per test
- **Core Counts**: 1, 2, 3, 4, 5, 6, 7, 8 (auto-detected)
- **Core Pinning**: Uses `taskset` to pin threads to specific cores
- **Config File**: `config/local-tpcc-baseline.yml` or `config/mako_single_node.yml`

### What Happens During a Test

1. **Setup**: Script detects available cores and prepares test environment
2. **Execution**: For each core count:
   - Pins threads to cores 0 to (N-1)
   - Runs TPC-C benchmark for specified duration
   - Collects performance metrics
3. **Data Collection**: Extracts throughput, latency, abort rates from logs
4. **Storage**: Saves results as JSON files and detailed logs

### Output Structure

```
results/
├── baseline_performance/
│   ├── baseline_1cores.log
│   ├── baseline_1cores.json
│   ├── baseline_2cores.log
│   ├── baseline_2cores.json
│   └── ...
└── parallel_batch_validation/
    ├── parallel_1cores.log
    ├── parallel_1cores.json
    └── ...
```

---

## Running Baseline Tests

### Quick Start

```bash
cd /home/ubuntu/mako
./test_baseline_performance_tpcc.sh
```

### What This Does

1. ✅ Checks for `dbtest` binary
2. ✅ Verifies config file exists
3. ✅ Disables batch validation (baseline mode)
4. ✅ Tests with 1, 2, 3, 4, 5, 6, 7, 8 cores
5. ✅ Runs 30 seconds per configuration
6. ✅ Saves results to `results/baseline_performance/`

### Expected Output

```
==========================================
TPC-C Baseline Performance Test
==========================================

Baseline Configuration:
  Batch validation: DISABLED
  Duration: 30 seconds per test
  Binary: build/dbtest
  Config: config/local-tpcc-baseline.yml

System Information:
  Total cores available: 8
  Physical cores: 4

Testing core counts: 1 2 3 4 5 6 7 8

Testing with 1 core(s)...
  Core mask: 0
  Pinning to cores: 0-0
  Starting benchmark...
  Completed in 32.5s
  ✓ Results saved to: results/baseline_performance/baseline_1cores.json

[... continues for each core count ...]
```

### Time Estimate

- **Per test**: ~30-35 seconds (30s benchmark + overhead)
- **Total time**: ~4-5 minutes for all 8 core counts

### Verify Results

```bash
# Check JSON files were created
ls -lh results/baseline_performance/*.json

# View a sample result
cat results/baseline_performance/baseline_8cores.json

# Check logs
tail -20 results/baseline_performance/baseline_8cores.log
```

---

## Running Parallel Batch Validation Tests

### Prerequisites

**Important**: Mako must be built with batch validation enabled:

```bash
cd /home/ubuntu/mako/build
cmake .. -DENABLE_BATCH_VALIDATION=ON -DENABLE_OPENMP=ON
make -j$(nproc)
cd ..
```

### Quick Start

```bash
cd /home/ubuntu/mako
./test_parallel_batch_validation_tpcc.sh
```

### What This Does

1. ✅ Checks for `dbtest` binary (with batch validation support)
2. ✅ Verifies config file exists
3. ✅ **Enables** batch validation (parallel mode)
4. ✅ Sets batch size to 32 (default)
5. ✅ Sets max wait time to 1000 microseconds (default)
6. ✅ Tests with 1, 2, 3, 4, 5, 6, 7, 8 cores
7. ✅ Runs 30 seconds per configuration
8. ✅ Saves results to `results/parallel_batch_validation/`

### Expected Output

```
==========================================
TPC-C Parallel Batch Validation Test
==========================================

Parallel Batch Validation Configuration:
  Batch validation: ENABLED
  Batch size: 32
  Max wait time: 1000 microseconds
  Duration: 30 seconds per test
  Binary: build/dbtest
  Config: config/local-tpcc-baseline.yml

Testing with 1 core(s) (Parallel Batch Validation)...
  Core mask: 0
  Pinning to cores: 0-0
  Starting benchmark...
  Completed in 33.2s
  ✓ Results saved to: results/parallel_batch_validation/parallel_1cores.json

[... continues for each core count ...]
```

### Time Estimate

- **Per test**: ~30-35 seconds
- **Total time**: ~4-5 minutes for all 8 core counts

### Verify Results

```bash
# Check JSON files were created
ls -lh results/parallel_batch_validation/*.json

# View a sample result
cat results/parallel_batch_validation/parallel_8cores.json
```

---

## Comparing Results

### Quick Start

After running both baseline and parallel tests:

```bash
cd /home/ubuntu/mako
python3 compare_baseline_parallel.py
```

### What This Does

1. ✅ Loads baseline results from `results/baseline_performance/`
2. ✅ Loads parallel results from `results/parallel_batch_validation/`
3. ✅ Calculates speedup and improvement percentages
4. ✅ Generates comparison visualizations
5. ✅ Saves comparison data to `results/comparison/`

### Generated Output

```
results/comparison/
├── comparison.json              # Detailed comparison data
├── throughput_comparison.png    # Throughput comparison chart
├── efficiency_comparison.png    # Per-core efficiency comparison
├── abort_rate_comparison.png    # Abort rate comparison
└── comparison_dashboard.png     # Comprehensive dashboard
```

### Console Output

```
================================================================================
PERFORMANCE COMPARISON: Baseline vs Parallel Batch Validation
================================================================================

Cores  Baseline     Parallel     Speedup  Improvement 
--------------------------------------------------------------------------------
1          69,946      70,320    1.01x         0.5%
2         134,877     136,551    1.01x         1.2%
3         194,681     195,071    1.00x         0.2%
4         229,148     228,303    1.00x        -0.4%
5         265,492     261,885    0.99x        -1.4%
6         306,093     316,956    1.04x         3.5%
7         345,545     346,582    1.00x         0.3%
8         348,839     352,806    1.01x         1.1%

================================================================================
KEY INSIGHTS
================================================================================
✅ Maximum Speedup: 1.04x at 6 cores
✅ Average Speedup: 1.01x
✅ Maximum Improvement: 3.5%
✅ Average Improvement: 0.7%
================================================================================
```

### View Visualizations

```bash
# View comparison dashboard
xdg-open results/comparison/comparison_dashboard.png

# Or on headless systems, copy to local machine
scp results/comparison/*.png user@local-machine:/path/to/save/
```

---

## Understanding the Results

### JSON File Structure

Each test generates a JSON file with the following structure:

```json
{
  "core_count": 8,
  "duration_seconds": 30,
  "actual_duration": 32.5,
  "cpu_frequency_khz": "2400000",
  "throughput": {
    "txns_per_second": 348839.0,
    "committed": 10558657,
    "aborted": 2160
  },
  "configuration": {
    "batch_validation": false,  // or true for parallel tests
    "batch_size": 32,            // only for parallel tests
    "max_wait_us": 1000,         // only for parallel tests
    "workload": "tpcc",
    "scale_factor": 8
  },
  "batch_validation_stats": {    // only for parallel tests
    "batch_validations": 12345,
    "batch_validated_txns": 10500000,
    "batch_aborted_txns": 2000,
    "avg_batch_size": 28.5
  },
  "output_file": "results/baseline_performance/baseline_8cores.log"
}
```

### Key Metrics Explained

#### Throughput (txns_per_second)
- **What**: Number of transactions processed per second
- **Higher is better**: Indicates better performance
- **Typical range**: 50,000 - 400,000+ depending on core count

#### Latency (avg_latency_ms)
- **What**: Average time to complete a transaction
- **Lower is better**: Faster transaction processing
- **Typical range**: 0.01 - 0.05 ms for TPC-C

#### Abort Rate (%)
- **What**: Percentage of transactions that fail validation
- **Lower is better**: Fewer conflicts
- **Typical range**: 0% - 5% for TPC-C

#### Per-Core Throughput
- **What**: Throughput divided by number of cores
- **Use**: Measures scaling efficiency
- **Ideal**: Constant (perfect scaling)
- **Reality**: Usually decreases with more cores (contention)

#### Speedup
- **What**: Parallel throughput / Baseline throughput
- **> 1.0**: Parallel is faster
- **< 1.0**: Parallel is slower
- **1.0**: No difference

### Interpreting Results

#### Good Scaling
- Throughput increases roughly linearly with core count
- Per-core throughput stays relatively constant
- Abort rate remains low

#### Poor Scaling
- Throughput plateaus or decreases with more cores
- Per-core throughput drops significantly
- Abort rate increases dramatically

#### Parallel vs Baseline
- **Speedup > 1.0**: Parallel batch validation helps
- **Speedup < 1.0**: Overhead outweighs benefits
- **Best at higher cores**: Usually shows more benefit with more contention

---

## Customization Options

### Test Specific Core Counts

Instead of testing all cores 1-8, test only specific ones:

```bash
CORE_COUNTS="1 2 4 8" ./test_baseline_performance_tpcc.sh
CORE_COUNTS="1 2 4 8" ./test_parallel_batch_validation_tpcc.sh
```

### Change Test Duration

Edit the script or set environment variable:

```bash
# In the script, change:
DURATION=60  # 60 seconds instead of 30

# Or create a wrapper:
export DURATION=60
./test_baseline_performance_tpcc.sh
```

### Adjust Batch Validation Parameters

For parallel tests only:

```bash
# Larger batch size (more transactions per batch)
MAKO_BATCH_VALIDATION_SIZE=64 ./test_parallel_batch_validation_tpcc.sh

# Longer wait time (wait more before validating incomplete batch)
MAKO_BATCH_VALIDATION_MAX_WAIT_US=2000 ./test_parallel_batch_validation_tpcc.sh

# Both together
MAKO_BATCH_VALIDATION_SIZE=64 MAKO_BATCH_VALIDATION_MAX_WAIT_US=2000 \
  ./test_parallel_batch_validation_tpcc.sh
```

### Use Different Config File

Edit the script to change `CONFIG_FILE` variable:

```bash
# In test_baseline_performance_tpcc.sh or test_parallel_batch_validation_tpcc.sh
CONFIG_FILE="config/your-custom-config.yml"
```

### Test All Available Cores

By default, tests cap at 8 cores. To test all available cores:

```bash
TEST_ALL_CORES=1 MAX_CORES=16 ./test_baseline_performance_tpcc.sh
```

---

## Troubleshooting

### "Binary not found"

**Error**: `ERROR: Binary not found at build/dbtest`

**Solution**:
```bash
# Build Mako first
cd /home/ubuntu/mako/build
cmake ..
make -j$(nproc)
cd ..
```

### "Config file not found"

**Error**: `ERROR: Config file not found: config/local-tpcc-baseline.yml`

**Solution**:
```bash
# Check available config files
ls config/*.yml

# Edit the script to use an available config file
# Or create the missing config file
```

### "Permission denied"

**Error**: `Permission denied` when running script

**Solution**:
```bash
chmod +x test_baseline_performance_tpcc.sh
chmod +x test_parallel_batch_validation_tpcc.sh
```

### "Batch validation not working"

**Symptoms**: Parallel tests show same results as baseline

**Solution**:
1. Verify build has batch validation enabled:
   ```bash
   cd build
   cmake -L . | grep BATCH_VALIDATION
   # Should show: ENABLE_BATCH_VALIDATION:BOOL=ON
   ```

2. Check environment variables:
   ```bash
   echo $MAKO_ENABLE_BATCH_VALIDATION  # Should be "1"
   ```

3. Rebuild if needed:
   ```bash
   cd build
   cmake .. -DENABLE_BATCH_VALIDATION=ON -DENABLE_OPENMP=ON
   make -j$(nproc)
   ```

### "No speedup observed"

**Possible reasons**:
- Low contention workload (batch validation helps most under high contention)
- OpenMP not properly linked
- Batch size too small or too large
- System has few cores (benefits increase with more cores)

**Solutions**:
- Try higher core counts (4-8 cores)
- Increase batch size: `MAKO_BATCH_VALIDATION_SIZE=64`
- Check OpenMP is available: `gcc -fopenmp --version`

### "Tests timeout"

**Error**: Benchmark times out after duration

**Solution**:
- Increase timeout in script (currently `DURATION + 120` seconds)
- Check system resources (CPU, memory)
- Reduce test duration if system is slow

### "JSON parsing errors"

**Error**: `Expecting value: line X column Y`

**Solution**:
- Check log files for actual errors
- The comparison script handles some JSON issues automatically
- Manually fix JSON files if needed (remove empty values)

### "Python packages missing"

**Error**: `ModuleNotFoundError: No module named 'pandas'`

**Solution**:
```bash
pip3 install pandas matplotlib seaborn numpy
```

---

## Advanced Usage

### Manual Benchmark Execution

Instead of using the scripts, run benchmarks manually:

```bash
# Baseline (no batch validation)
unset MAKO_ENABLE_BATCH_VALIDATION
taskset -c 0-3 \
  ./build/dbtest \
  --site-name local_s0 \
  --num-threads 4 \
  --shard-config config/local-tpcc-baseline.yml \
  --shard-index 0 \
  > results/manual_baseline_4cores.log 2>&1

# Parallel (with batch validation)
export MAKO_ENABLE_BATCH_VALIDATION=1
export MAKO_BATCH_VALIDATION_SIZE=32
taskset -c 0-3 \
  ./build/dbtest \
  --site-name local_s0 \
  --num-threads 4 \
  --shard-config config/local-tpcc-baseline.yml \
  --shard-index 0 \
  > results/manual_parallel_4cores.log 2>&1
```

### Extracting Metrics from Logs

```bash
# Throughput
grep -i "throughput" results/baseline_performance/baseline_8cores.log

# Commit/abort counts
grep "n_commits:" results/baseline_performance/baseline_8cores.log
grep "agg_abort_rate:" results/baseline_performance/baseline_8cores.log

# Batch validation stats (parallel tests only)
grep "g_evt_batch" results/parallel_batch_validation/parallel_8cores.log
```

### Creating Custom Visualizations

Modify `compare_baseline_parallel.py` or create your own script:

```python
import json
import pandas as pd
import matplotlib.pyplot as plt

# Load your data
with open('results/baseline_performance/baseline_8cores.json') as f:
    baseline = json.load(f)

# Create custom plots
# ... your visualization code ...
```

### Batch Testing Multiple Configurations

Create a wrapper script to test multiple batch sizes:

```bash
#!/bin/bash
for batch_size in 16 32 64 128; do
    echo "Testing batch size: $batch_size"
    MAKO_BATCH_VALIDATION_SIZE=$batch_size \
      ./test_parallel_batch_validation_tpcc.sh
    mv results/parallel_batch_validation \
       results/parallel_batch_${batch_size}
done
```

### Automated Testing Pipeline

Create a script to run everything:

```bash
#!/bin/bash
set -e

echo "Step 1: Build baseline"
cd build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
make -j$(nproc)
cd ..

echo "Step 2: Run baseline tests"
./test_baseline_performance_tpcc.sh

echo "Step 3: Rebuild with batch validation"
cd build
cmake .. -DENABLE_BATCH_VALIDATION=ON -DENABLE_OPENMP=ON
make -j$(nproc)
cd ..

echo "Step 4: Run parallel tests"
./test_parallel_batch_validation_tpcc.sh

echo "Step 5: Compare results"
python3 compare_baseline_parallel.py

echo "Done! Check results/comparison/ for visualizations"
```

---

## Quick Reference

### Common Commands

```bash
# Build baseline
cd build && cmake .. -DENABLE_BATCH_VALIDATION=OFF && make -j$(nproc) && cd ..

# Build parallel
cd build && cmake .. -DENABLE_BATCH_VALIDATION=ON -DENABLE_OPENMP=ON && make -j$(nproc) && cd ..

# Run baseline
./test_baseline_performance_tpcc.sh

# Run parallel
./test_parallel_batch_validation_tpcc.sh

# Compare
python3 compare_baseline_parallel.py

# View results
ls -lh results/comparison/*.png
cat results/comparison/comparison.json
```

### File Locations

| File/Directory | Purpose |
|----------------|---------|
| `test_baseline_performance_tpcc.sh` | Baseline test script |
| `test_parallel_batch_validation_tpcc.sh` | Parallel test script |
| `compare_baseline_parallel.py` | Comparison script |
| `results/baseline_performance/` | Baseline test results |
| `results/parallel_batch_validation/` | Parallel test results |
| `results/comparison/` | Comparison analysis and charts |
| `build/dbtest` | Benchmark binary |
| `config/local-tpcc-baseline.yml` | Test configuration |

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `MAKO_ENABLE_BATCH_VALIDATION` | Enable batch validation | Not set (disabled) |
| `MAKO_BATCH_VALIDATION_SIZE` | Transactions per batch | 32 |
| `MAKO_BATCH_VALIDATION_MAX_WAIT_US` | Max wait time (μs) | 1000 |
| `CORE_COUNTS` | Core counts to test | Auto (1-8) |
| `TEST_ALL_CORES` | Test all available cores | 1 (true) |
| `DURATION` | Test duration (seconds) | 30 |

---

## Next Steps

1. ✅ Run baseline tests to establish baseline performance
2. ✅ Run parallel tests to measure parallel batch validation
3. ✅ Compare results to see improvements
4. 📊 Analyze visualizations to understand scaling behavior
5. 🔧 Experiment with different batch sizes and configurations
6. 📈 Document your findings and optimizations

---

## Additional Resources

- `RUN_BASELINE_STEPS.md` - Quick baseline testing guide
- `RUN_PARALLEL_TESTING.md` - Parallel testing guide
- `PARALLEL_VALIDATION.md` - Technical details on parallel batch validation
- `BASELINE_PERFORMANCE_TESTING.md` - Detailed baseline testing documentation

---

**Happy Benchmarking!** 🚀


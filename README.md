# Understanding When Batch Validation Helps: A Performance Study of OCC in Mako

[![Paper](https://img.shields.io/badge/Paper-LaTeX-blue)](paper.tex)
[![Poster](https://img.shields.io/badge/Poster-Google%20Slides-red)](https://docs.google.com/presentation/d/1Co1du3xVOuVIveardhS0Ufb0FP91fcFcbYnB3bS9yjM/edit?usp=sharing)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-green)](https://github.com/dors20/mako-eocc)

## Overview

This repository contains a comprehensive performance study of **batch validation** in Optimistic Concurrency Control (OCC) systems, specifically implemented in the [Mako](https://github.com/dors20/mako-eocc) database system. The work investigates when and why batch validation provides performance benefits, using a systematic two-phase microbenchmarking methodology combined with CPU profiling and end-to-end evaluation.

### Research Question

**When does batch validation help, and why does it sometimes hurt performance?**

We answer this through:
- **Pure validation microbenchmarks** - Isolating validation logic to measure theoretical speedup
- **Full lifecycle microbenchmarks** - Measuring complete transaction lifecycle with realistic time fractions
- **End-to-end TPC-C evaluation** - Production workload performance analysis
- **CPU profiling** - Identifying bottlenecks using `perf` and flamegraphs

### Key Findings

1. **Pure validation microbenchmark**: Shows 4.56× speedup (validation-only parallelization works)
2. **Full lifecycle microbenchmark**: Shows 0.99× speedup (validation is only 10-15% of total time)
3. **TPC-C production workload**: Shows -70.3% throughput reduction and +250.5% latency increase

**Critical insight**: Even perfect validation parallelization provides minimal benefit when validation represents a small fraction of total transaction time, as predicted by Amdahl's Law.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Microbenchmarks](#microbenchmarks)
  - [Pure Validation Microbenchmark](#pure-validation-microbenchmark)
  - [Full Lifecycle Microbenchmark](#full-lifecycle-microbenchmark)
- [OCC Test Suite](#occ-test-suite)
- [Building and Running](#building-and-running)
- [Understanding Results](#understanding-results)
- [Analysis Documents](#analysis-documents)
- [Paper and Poster](#paper-and-poster)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

### Prerequisites

- **Compiler**: GCC 12+ with C++17 support
- **OpenMP**: Required for parallel validation (`libomp-dev` on Ubuntu/Debian)
- **CMake**: Version 3.10 or higher
- **Python 3**: For graph generation scripts (requires `matplotlib`, `pandas`, `numpy`)

### Build Microbenchmarks

```bash
# Clone the repository
git clone https://github.com/dors20/mako-eocc.git
cd mako-eocc

# Create build directory
mkdir -p build && cd build

# Configure with CMake
cmake ..

# Build microbenchmarks
make test_parallel_validation_micro
make test_parallel_validation_micro_full_lifecycle

# Executables will be in build/
```

### Run a Quick Test

```bash
# Run pure validation microbenchmark
cd build
OMP_NUM_THREADS=8 ./test_parallel_validation_micro

# Run full lifecycle microbenchmark
OMP_NUM_THREADS=8 ./test_parallel_validation_micro_full_lifecycle
```

---

## Project Structure

```
mako/
├── README.md                          # This file
├── paper.tex                          # Research paper (LaTeX)
├── CMakeLists.txt                     # Build configuration
│
├── test_parallel_validation_micro.cc              # Pure validation microbenchmark
├── test_parallel_validation_micro_full_lifecycle.cc  # Full lifecycle microbenchmark
│
├── results/
│   ├── perf_profiles/
│   │   ├── parallel_validation_results.csv       # Pure microbenchmark results
│   │   ├── full_lifecycle_results.csv            # Full lifecycle results
│   │   ├── FINAL_BATCH_VALIDATION_ANALYSIS.md     # Comprehensive analysis
│   │   └── MICROBENCHMARK_METHODOLOGY.md          # Methodology narrative
│   └── dbtest_comparison.csv                     # TPC-C comparison results
│
├── results_for_report/
│   ├── generate_microbenchmark_graphs.py         # Graph generation scripts
│   ├── generate_full_lifecycle_graphs.py
│   ├── generate_dbtest_graphs.py
│   └── *.png                                     # Generated graphs
│
├── MICROBENCHMARK_GUIDE.md                       # Detailed microbenchmark guide
└── BATCHING_MICRO_BENCHMARK_FINDINGS.md         # Batching findings
```

---

## Microbenchmarks

### Pure Validation Microbenchmark

**Purpose**: Measure validation speedup in isolation, eliminating all other system overheads.

**What it tests**:
- Pure validation logic (read/write set version checking)
- No Masstree traversal
- No batching synchronization overhead
- No storage phase
- No system calls

**Usage**:

```bash
cd build

# Basic run with default parameters
./test_parallel_validation_micro

# Custom thread count
OMP_NUM_THREADS=16 ./test_parallel_validation_micro

# Generate CSV output
./test_parallel_validation_micro --csv
```

**Output**:
- Console tables showing throughput and speedup
- CSV file: `results/perf_profiles/parallel_validation_results.csv`

**Expected Results**:
- **Speedup**: 4-5× for large batches (128-512 transactions)
- **Throughput**: Scales with thread count up to ~8-16 threads
- **Key insight**: Validation parallelization works when isolated

**Generate Graphs**:

```bash
python3 results_for_report/generate_microbenchmark_graphs.py
```

Graphs saved to `results_for_report/`:
- `speedup_summary.png` - Speedup vs batch size
- `thread_count_impact.png` - Thread scaling
- `readset_size_impact.png` - Read set size impact

---

### Full Lifecycle Microbenchmark

**Purpose**: Measure complete transaction lifecycle with realistic time fractions to predict real-world performance.

**What it tests**:
- **Execution phase** (65% of time): Masstree lookups, business logic (NOT parallelizable)
- **Validation phase** (12.5% of time): Read/write set validation (CAN be parallelized)
- **Storage phase** (17.5% of time): Sequential writes (NOT parallelizable)
- **Other overheads** (5% of time): System overheads

**Usage**:

```bash
cd build

# Basic run with realistic time fractions
./test_parallel_validation_micro_full_lifecycle

# Custom execution ratio (default: 0.65)
EXECUTION_RATIO=0.70 ./test_parallel_validation_micro_full_lifecycle

# Custom thread count
OMP_NUM_THREADS=8 ./test_parallel_validation_micro_full_lifecycle

# Generate CSV output
./test_parallel_validation_micro_full_lifecycle --csv
```

**Output**:
- Console tables showing throughput and speedup
- CSV file: `results/perf_profiles/full_lifecycle_results.csv`

**Expected Results**:
- **Speedup**: ~0.99× (minimal improvement)
- **Throughput**: Slight improvement or degradation
- **Key insight**: Even perfect validation parallelization provides minimal benefit when validation is only 10-15% of total time

**Generate Graphs**:

```bash
python3 results_for_report/generate_full_lifecycle_graphs.py
```

Graphs saved to `results_for_report/`:
- `full_lifecycle_combined_summary.png` - Combined throughput and speedup
- `full_lifecycle_batch_size_throughput.png` - Batch size impact
- `full_lifecycle_thread_count_speedup.png` - Thread scaling

---

## OCC Test Suite

**Purpose**: Comprehensive test suite for evaluating OCC optimizations (batch validation, transaction reordering, storage reordering, parallel validation) across multiple workloads.

The OCC test suite contains **30 test scenarios** that systematically test various combinations of OCC optimizations on different workloads, from simple transactions to full TPC-C benchmarks.

### Test Categories

1. **Simple Transaction Tests** (3 tests): Minimal transaction workload using `simpleTransaction`
2. **Stress Harness Tests** (12 tests): Synthetic stress tests with varying concurrency
3. **TPC-C Tests** (15 tests): Full TPC-C benchmark with different optimization combinations

### Quick Start

```bash
# Build required binaries first
cd build
cmake ..
make -j$(nproc) dbtest simpleTransaction test_batch_validation_stress
cd ..

# Run all tests in fast mode (quick testing, ~5-10 minutes)
python3 scripts/run_occ_suite.py --mode fast

# Run all tests in full mode (comprehensive testing, ~30-60 minutes)
python3 scripts/run_occ_suite.py --mode full
```

### Running Specific Tests

```bash
# Run only baseline and batch validation TPC-C tests
python3 scripts/run_occ_suite.py --mode fast --only dbtest_baseline_tpcc dbtest_batch_validation_tpcc

# Run with custom thread count
python3 scripts/run_occ_suite.py --mode fast --override-threads 8

# Dry run (show commands without executing)
python3 scripts/run_occ_suite.py --mode fast --dry-run
```

### Key Test Scenarios

**Most Important Tests**:
- `dbtest_baseline_tpcc` - Baseline OCC for comparison
- `dbtest_batch_validation_tpcc` - Core batch validation feature
- `dbtest_batch_validation_reorder_prod` - Batch validation + production reordering
- `dbtest_batch_validation_all_optimizations` - All optimizations combined
- `dbtest_baseline_tpcc_1wh_hot` - High contention baseline
- `dbtest_batch_validation_tpcc_1wh_hot` - High contention with batch validation

### Test Options

| Option | Description |
|-------|-------------|
| `--mode {fast,full}` | Choose fast (quick) or full (comprehensive) mode |
| `--only {test1} {test2} ...` | Run only specified tests |
| `--override-threads N` | Override thread count for all tests |
| `--threads-fraction F` | Set threads to `cpu_count() * F` |
| `--dry-run` | Show commands without executing |
| `--results-root PATH` | Custom results directory |
| `--scenarios PATH` | Custom scenarios YAML file |

### Test Modes

**Fast Mode** (for quick testing):
- Runtime: 5 seconds
- Threads: 2
- Batch size: 8
- Batch wait: 250μs

**Full Mode** (for comprehensive testing):
- Runtime: 60 seconds
- Threads: 24
- Batch size: 16
- Batch wait: 500μs

### Optimization Features Tested

| Feature | Environment Variables |
|---------|---------------------|
| **Batch Validation** | `MAKO_ENABLE_BATCH_VALIDATION=1`<br>`MAKO_BATCH_VALIDATION_SIZE={size}`<br>`MAKO_BATCH_VALIDATION_MAX_WAIT_US={us}` |
| **Transaction Reordering** | `MAKO_ENABLE_TXN_REORDER=1`<br>`MAKO_TXN_REORDER_FVS={min\|prod}`<br>`MAKO_TXN_REORDER_ALGO=sort` |
| **Storage Reordering** | `MAKO_ENABLE_STORAGE_REORDER=1`<br>`MAKO_STORAGE_REORDER_SIZE={size}`<br>`MAKO_STORAGE_REORDER_MAX_WAIT_US={us}` |
| **Parallel Validation** | `MAKO_BATCH_VALIDATION_THREADS={n}`<br>`OMP_NUM_THREADS={n}` |

### Results

Test results are stored in:
```
results/occ_runs/{timestamp}_{mode}/{test_name}/
├── stdout.log          # Test output with metrics
├── metadata.json       # Test configuration
└── ...
```

Summary metrics are aggregated in:
```
results/occ_runs/{timestamp}_{mode}/summary_metrics.csv
```

### Example Output

After running tests, you'll see:
- Throughput (TPS - transactions per second)
- Latency (average, p50, p95, p99)
- Abort rate
- Commit rate
- Comparison with baseline

### Documentation

For complete test suite documentation, see:
- **`OCC_TEST_SUITE_OVERVIEW.md`** - Complete test matrix and descriptions
- **`config/occ_experiments.yml`** - Test configuration file

---

## Building and Running

### Full Build Process

```bash
# 1. Install dependencies (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    libomp-dev \
    python3 \
    python3-pip \
    python3-matplotlib \
    python3-pandas \
    python3-numpy

# 2. Clone and build
git clone https://github.com/dors20/mako-eocc.git
cd mako-eocc
mkdir -p build && cd build
cmake ..
make -j$(nproc) test_parallel_validation_micro test_parallel_validation_micro_full_lifecycle

# 3. Run microbenchmarks
OMP_NUM_THREADS=8 ./test_parallel_validation_micro
OMP_NUM_THREADS=8 ./test_parallel_validation_micro_full_lifecycle

# 4. Generate graphs
cd ..
python3 results_for_report/generate_microbenchmark_graphs.py
python3 results_for_report/generate_full_lifecycle_graphs.py
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OMP_NUM_THREADS` | Number of OpenMP threads for parallel validation | 8 |
| `EXECUTION_RATIO` | Fraction of time in execution phase (full lifecycle only) | 0.65 |
| `CACHE_MISS_RATE` | Cache miss rate for Masstree simulation | 0.3 |

### Command-Line Options

**Pure Validation Microbenchmark**:
```bash
./test_parallel_validation_micro [--csv]
```

**Full Lifecycle Microbenchmark**:
```bash
./test_parallel_validation_micro_full_lifecycle [--csv] [--execution-ratio=X]
```

---

## Understanding Results

### Interpreting Microbenchmark Results

#### Pure Validation Microbenchmark

**What good results look like**:
- Speedup increases with batch size (up to 4-5×)
- Throughput scales with thread count
- Large read sets show better speedup (more work to parallelize)

**What this means**:
- Validation parallelization **works** when isolated
- Proves the optimization is **technically sound**
- But **doesn't predict real-world performance**

#### Full Lifecycle Microbenchmark

**What realistic results look like**:
- Speedup near 1.0× (minimal improvement)
- Throughput may decrease slightly
- Thread scaling plateaus quickly

**What this means**:
- Validation is only 10-15% of total transaction time
- Execution and storage phases dominate (65% + 17.5% = 82.5%)
- Amdahl's Law: parallelizing 12.5% of work can't provide large speedup

### Key Metrics

| Metric | Pure Microbenchmark | Full Lifecycle | TPC-C Reality |
|-------|-------------------|----------------|---------------|
| **Speedup** | 4.56× | 0.99× | -70.3% throughput |
| **Validation Time Fraction** | 100% | 12.5% | 10-15% |
| **Predictive Accuracy** | Low | High | N/A |

### Why the Disconnect?

1. **Time fraction**: Validation is only 10-15% of total transaction time
2. **Sequential bottlenecks**: Execution (65%) and storage (17.5%) are not parallelizable
3. **Amdahl's Law**: Maximum speedup = 1 / (1 - P + P/N), where P is parallelizable fraction
   - For P = 0.125 (12.5%), even infinite parallelism gives < 1.15× speedup
4. **Batching overhead**: Additional latency from waiting for batches to fill
5. **Higher abort rates**: Batching can increase conflicts and aborts

---

## Analysis Documents

Comprehensive analysis documents are available in `results/perf_profiles/`:

- **`FINAL_BATCH_VALIDATION_ANALYSIS.md`**: Complete performance analysis, CPU profiling results, and bottleneck identification
- **`MICROBENCHMARK_METHODOLOGY.md`**: Narrative explanation of the two-phase microbenchmarking approach
- **`REALISM_ANALYSIS.md`**: Comparison of microbenchmark realism vs. TPC-C reality
- **`BATCHING_MICRO_BENCHMARK_FINDINGS.md`**: Detailed findings from batching experiments

---

## Paper and Poster

- **Paper**: See `paper.tex` for the complete research paper (LaTeX source)
- **Poster**: [Google Slides Presentation](https://docs.google.com/presentation/d/1Co1du3xVOuVIveardhS0Ufb0FP91fcFcbYnB3bS9yjM/edit?usp=sharing)
- **GitHub**: [Repository](https://github.com/dors20/mako-eocc)

### Compiling the Paper

```bash
# Install LaTeX dependencies (Ubuntu/Debian)
sudo apt-get install -y texlive-latex-base texlive-latex-extra texlive-fonts-recommended

# Compile paper
pdflatex paper.tex
bibtex paper  # If using bibliography
pdflatex paper.tex
pdflatex paper.tex  # Run twice for references
```

---

## Contributing

This is a research repository. For questions or issues:

1. Open an issue on GitHub
2. Contact the authors (see paper.tex for author list)
3. Refer to the analysis documents for detailed methodology

---

## License

This work is part of the Mako database system. See the main repository for license information.

---

## Citation

If you use this work in your research, please cite:

```bibtex
@article{batch_validation_occ_mako,
  title={Understanding When Batch Validation Helps: A Performance Study of OCC in Mako},
  author={Kong, Adrian and Lin, Irvin and Dorsala, Mahesh and Li, Shaoyang and Vyamajala, Vishal},
  year={2025},
  note={GitHub: \url{https://github.com/dors20/mako-eocc}}
}
```

---

## Authors

- Adrian Kong
- Irvin Lin
- Mahesh Dorsala
- Shaoyang Li
- Vishal Vyamajala

---

## Acknowledgments

This work builds on the [Mako](https://github.com/dors20/mako-eocc) database system and investigates batch validation optimizations for Optimistic Concurrency Control (OCC).

---

*Last updated: December 2025*

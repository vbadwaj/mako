# Baseline Performance Visualizations

This directory contains a Jupyter notebook for visualizing the baseline performance results from TPC-C benchmark runs.

## Quick Start

### 1. Install Required Python Packages

```bash
pip install jupyter pandas matplotlib seaborn numpy
```

### 2. Launch Jupyter Notebook

```bash
cd /home/ubuntu/mako
jupyter notebook visualize_baseline_performance.ipynb
```

Or use JupyterLab:
```bash
jupyter lab visualize_baseline_performance.ipynb
```

### 3. Run All Cells

In Jupyter, click `Cell` → `Run All` to execute all cells and generate all visualizations.

## Notebook Contents

The notebook includes the following visualizations:

1. **Throughput Scaling**
   - Total throughput vs core count
   - Per-core throughput efficiency
   - Scaling efficiency analysis

2. **Latency Analysis**
   - Average transaction latency by core count
   - Per-transaction-type latency breakdown
   - Latency comparison across transaction types

3. **Abort Rate Analysis**
   - Abort rate percentage by core count
   - Absolute abort counts

4. **Comprehensive Performance Dashboard**
   - Multi-panel dashboard showing:
     - Throughput scaling (with ideal scaling reference)
     - Per-core efficiency
     - Average latency
     - Abort rates
     - Speedup comparison
     - Transaction type latency heatmap

5. **Summary Statistics**
   - Comprehensive performance summary table
   - Key insights and metrics

## Output

The notebook generates:
- Multiple detailed plots showing performance trends
- Summary tables with key metrics
- Efficiency calculations (speedup, scaling efficiency)
- Key insights highlighting peak performance points

## Data Source

The notebook reads from:
- `results/baseline_performance/summary.json` - Aggregated performance data

All visualizations are generated automatically from this data.


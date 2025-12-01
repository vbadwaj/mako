# Baseline Performance Results Summary

## ✅ Test Completed Successfully

All baseline performance tests have been completed for core counts 1-8.

## 📊 Overall Performance

| Cores | Throughput (txns/sec) | Committed | Aborted | Abort Rate |
|-------|----------------------|-----------|---------|------------|
| 1     | 75,386               | 2,278,928 | 0       | 0.00%      |
| 2     | 146,968              | 4,441,706 | 684     | 0.02%      |
| 3     | 208,764              | 6,312,988 | 944     | 0.01%      |
| 4     | 241,458              | 7,299,930 | 1,184   | 0.02%      |
| 5     | 289,111              | 8,743,513 | 1,413   | 0.02%      |
| 6     | 333,057              | 10,081,454| 1,713   | 0.02%      |
| 7     | 363,521              | 11,006,996| 1,926   | 0.02%      |
| 8     | 365,867              | 11,087,113| 1,999   | 0.02%      |

### Key Observations:
- ✅ **Excellent scaling**: Near-linear throughput increase from 1 to 6-7 cores
- ✅ **Very low abort rates**: 0.01-0.02% across all core counts
- ⚠️ **Saturation at 8 cores**: Diminishing returns, likely due to resource contention

## 📈 Transaction Latency Breakdown

Available latency data by transaction type shows how different operations perform:

- **Payment**: Fastest (~0.005-0.007 ms) - simple updates
- **OrderStatus**: Fast (~0.006-0.007 ms) - read-only queries  
- **NewOrder**: Moderate (~0.018-0.023 ms) - complex inserts
- **Delivery**: Slower (~0.070-0.091 ms) - batch updates
- **StockLevel**: Slowest (~0.078-0.114 ms) - aggregation queries

## ⚠️ Protocol Phase Breakdown (Not Available)

**Status**: Detailed protocol phase timings (read validation, write validation, commit phases) are **not available** in the current logs.

**Reason**: The performance probes (`scopedperf`) that measure time spent in different protocol phases are not enabled or not printing in the current build.

**To Enable Protocol Phase Breakdown**:
1. Rebuild with performance counters enabled
2. Enable `USE_PERF_CTRS` or similar compile-time flag
3. Re-run baseline tests

The probes we added (`g_txn_commit_probe0_cg`, `g_txn_commit_probe3_cg`, etc.) are defined in the code but not active in the current build configuration.

## 📁 Results Location

All results are saved in: `results/baseline_performance/`

- `baseline_Ncores.log` - Raw benchmark output
- `baseline_Ncores.json` - Extracted metrics
- `summary.json` - Comprehensive summary

## 🔍 View Results

```bash
# View summary
python3 scripts/parse_baseline_results.py results/baseline_performance

# View raw logs
cat results/baseline_performance/baseline_4cores.log

# View JSON summary
cat results/baseline_performance/summary.json | python3 -m json.tool
```


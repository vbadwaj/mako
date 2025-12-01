# 🚀 How to Run Parallel Batch Validation Testing

## Overview

**Baseline** = Sequential validation (one transaction at a time)  
**Parallel** = Batch validation with parallel processing (multiple transactions validated simultaneously)

You've already run the **baseline** tests. Now let's run the **parallel batch validation** tests to compare performance!

---

## Step 1: Build Mako with Batch Validation Enabled

The baseline was built **without** batch validation. For parallel testing, you need to rebuild with batch validation and OpenMP support:

```bash
cd /home/ubuntu/mako/build
cmake .. -DENABLE_BATCH_VALIDATION=ON -DENABLE_OPENMP=ON
make -j$(nproc)
cd ..
```

**Note:** This rebuilds Mako with parallel batch validation support. It may take a few minutes.

**OR use the automated script:**
```bash
./build_progressive.sh
```

---

## Step 2: Run Parallel Batch Validation Tests

Once built, run the parallel test script:

```bash
cd /home/ubuntu/mako
./test_parallel_batch_validation_tpcc.sh
```

This will:
- ✅ Test with cores: 1, 2, 3, 4, 5, 6, 7, 8
- ✅ Enable parallel batch validation
- ✅ Each test runs for 30 seconds
- ✅ Save results to `results/parallel_batch_validation/`

**Expected time:** ~4-5 minutes total

---

## Step 3: Compare Results

After both baseline and parallel tests are complete, you can compare them:

### Option 1: Manual Comparison
```bash
# View baseline results
cat results/baseline_performance/summary.json

# View parallel results  
cat results/parallel_batch_validation/parallel_8cores.json
```

### Option 2: Create Comparison Script (if needed)
You can create a script to automatically compare throughput, latency, and other metrics.

---

## Configuration Options

### Batch Size
Control how many transactions are validated together:
```bash
MAKO_BATCH_VALIDATION_SIZE=64 ./test_parallel_batch_validation_tpcc.sh
```

Default: 32 transactions per batch

### Max Wait Time
How long to wait (microseconds) before validating an incomplete batch:
```bash
MAKO_BATCH_VALIDATION_MAX_WAIT_US=2000 ./test_parallel_batch_validation_tpcc.sh
```

Default: 1000 microseconds

### Test Specific Cores
```bash
CORE_COUNTS="1 2 4 8" ./test_parallel_batch_validation_tpcc.sh
```

---

## What Gets Measured

### Same Metrics as Baseline:
- **Throughput**: Transactions per second
- **Latency**: Average transaction latency
- **Abort Rate**: Transaction abort percentage
- **Transaction Type Breakdown**: Per-transaction-type latencies

### Additional Parallel Metrics:
- **Batch Validations**: Number of batches processed
- **Batch Validated Transactions**: Transactions that passed batch validation
- **Batch Aborted Transactions**: Transactions aborted during batch validation
- **Average Batch Size**: Average number of transactions per batch

---

## Expected Results

With parallel batch validation, you should see:

✅ **Higher Throughput**: Especially at higher core counts (4-8 cores)  
✅ **Better CPU Utilization**: Multiple cores validating in parallel  
✅ **Similar or Lower Latency**: Depending on contention level  
✅ **Batch Statistics**: New metrics showing batch validation activity

---

## Quick Comparison

After running both tests, compare:

```bash
# Baseline throughput at 8 cores
grep "txns_per_second" results/baseline_performance/baseline_8cores.json

# Parallel throughput at 8 cores
grep "txns_per_second" results/parallel_batch_validation/parallel_8cores.json
```

---

## Troubleshooting

### "Binary not found"
Make sure you built with batch validation enabled (Step 1).

### "Batch validation not working"
Check that environment variables are set:
```bash
echo $MAKO_ENABLE_BATCH_VALIDATION  # Should be "1"
echo $MAKO_BATCH_VALIDATION_SIZE    # Should be set
```

### "No speedup observed"
- Batch validation helps most under **high contention**
- Try increasing thread count or workload intensity
- Check that OpenMP is enabled in the build

---

## Next Steps

1. ✅ Run baseline tests (you've done this!)
2. ✅ Build with batch validation enabled
3. ✅ Run parallel batch validation tests
4. 📊 Compare results and analyze improvements
5. 📈 Visualize the comparison (create comparison plots)

---

## Files Created

After running parallel tests:
```
results/parallel_batch_validation/
├── parallel_1cores.log
├── parallel_1cores.json
├── parallel_2cores.log
├── parallel_2cores.json
├── ...
└── parallel_8cores.log
└── parallel_8cores.json
```

---

## Summary

**Baseline** = Sequential validation (current standard)  
**Parallel** = Batch validation with parallel processing (optimization)

Run both, compare, and see the improvement! 🚀


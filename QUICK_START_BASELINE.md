# Quick Start: Running Baseline Performance Tests

## Step 1: Build Mako (if not already built)

```bash
cd build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
make -j2
cd ..
```

**Note:** Using `-j2` (2 parallel jobs) to avoid overwhelming your VM. Use `-j1` if it still crashes, or `-j4` if your VM can handle more.

**Or if already built**, just verify the binary exists:
```bash
ls build/benchmarks/dbtest
```

## Step 2: Run the Baseline Test

Simply run:

```bash
./test_baseline_performance_tpcc.sh
```

That's it! The script will:
- ✅ Auto-detect your available cores (8 cores on your system)
- ✅ Test with 1, 2, 3, 4, 5, 6, 7, 8 cores automatically
- ✅ Each test runs for 30 seconds
- ✅ Save results to `results/baseline_performance/`

## Step 3: View Results

After it finishes, parse the results:

```bash
python3 scripts/parse_baseline_results.py results/baseline_performance
```

This will show:
- Throughput for each core count
- Commit/abort statistics
- Protocol phase breakdowns

## What to Expect

The test will take approximately:
- **8 tests × 30 seconds = ~4 minutes** (plus setup/teardown)
- Plus time for data loading and parsing

You'll see output like:
```
==========================================
TPC-C Baseline Performance Test
==========================================

System Information:
  Total cores available: 8
  Physical cores: 4

Testing core counts: 1 2 3 4 5 6 7 8
  (Auto-testing all cores from 1 to 8)

Testing with 1 core(s)...
Testing with 2 core(s)...
...
```

## Troubleshooting

### "Binary not found"
```bash
cd build && cmake .. && make -j && cd ..
```

### "Config file not found"
Make sure you're in the Mako root directory:
```bash
pwd  # Should show /home/ubuntu/mako
ls config/local-shards2-warehouses1.yml  # Should exist
```

### Permission denied
If you get permission errors:
```bash
chmod +x test_baseline_performance_tpcc.sh
```

## Customizing

### Test only specific cores:
```bash
CORE_COUNTS="1 2 4 8" ./test_baseline_performance_tpcc.sh
```

### Change test duration:
Edit the script and change `DURATION=30` to your preferred seconds.

### Test all cores (no limit):
```bash
TEST_ALL_CORES=1 MAX_CORES=16 ./test_baseline_performance_tpcc.sh
```



# How Core Testing Works

## Key Point: Build ≠ Runtime Testing

- **`make -j8`**: Uses 8 cores to **compile** faster (just speeds up building)
- **Test script**: Controls which cores the **benchmark uses at runtime**

These are completely independent!

---

## How the Test Script Works

The `test_baseline_performance_tpcc.sh` script automatically tests different core counts using `taskset` to pin the benchmark to specific CPU cores.

### Default Behavior (Auto-tests all cores)

```bash
./test_baseline_performance_tpcc.sh
```

This will automatically test: **1, 2, 3, 4, 5, 6, 7, 8 cores**

Each test:
- Uses `taskset -c 0,1,2,3` (for 4 cores) to pin to specific CPUs
- Sets `--num-threads` to match the core count
- Runs for 30 seconds
- Saves results to `results/baseline_performance/`

---

## Customize Which Cores to Test

### Option 1: Test specific core counts only

```bash
CORE_COUNTS="1 2 4 8" ./test_baseline_performance_tpcc.sh
```

This will test only: **1, 2, 4, 8 cores** (faster)

---

### Option 2: Test all available cores (no 8-core limit)

```bash
TEST_ALL_CORES=1 MAX_CORES=16 ./test_baseline_performance_tpcc.sh
```

---

### Option 3: Test single core count

```bash
CORE_COUNTS="4" ./test_baseline_performance_tpcc.sh
```

---

## What Happens During Testing

For each core count (e.g., 4 cores):

1. **Pinning**: Uses `taskset -c 0,1,2,3` to pin to cores 0-3
2. **Threads**: Sets `--num-threads 4` to use 4 threads
3. **Isolation**: Benchmark only runs on those 4 cores
4. **Measurement**: Collects throughput, latency, phase breakdowns
5. **Save**: Writes results to `results/baseline_performance/baseline_4cores.log`

---

## Example Output

```
Testing core counts: 1 2 3 4 5 6 7 8

Testing with 1 core(s)...
  Core mask: 0
  Pinning to cores: 0
  Starting benchmark...

Testing with 2 core(s)...
  Core mask: 0,1
  Pinning to cores: 0-1
  Starting benchmark...

Testing with 4 core(s)...
  Core mask: 0,1,2,3
  Pinning to cores: 0-3
  Starting benchmark...
```

---

## Summary

✅ **Build with whatever you want**: `make -j1`, `-j4`, `-j8`, etc.  
   → This just affects compile time, not runtime testing

✅ **Test script handles core testing automatically**  
   → By default tests all cores 1-8

✅ **Customize if needed**  
   → Use `CORE_COUNTS="1 2 4 8"` to test specific counts only


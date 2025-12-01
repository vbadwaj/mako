# 🚀 How to Run Baseline Performance Test

## Simple 3-Step Process

### Step 1: Build Mako (if needed)

```bash
cd /home/ubuntu/mako
cd build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
make -j$(nproc)
cd ..
```

**Note:** Using `-j$(nproc)` to use all available CPU cores for faster compilation.

**OR use the automated script:**
```bash
./build_and_test.sh
```

**Skip this if `build/dbtest` already exists!**

---

### Step 2: Run the Test

```bash
cd /home/ubuntu/mako
./test_baseline_performance_tpcc.sh
```

That's it! The script will:
- ✅ Auto-detect your 8 cores
- ✅ Test with cores: 1, 2, 3, 4, 5, 6, 7, 8
- ✅ Each test runs for 30 seconds
- ✅ Save results to `results/baseline_performance/`

**Expected time:** ~4-5 minutes total

---

### Step 3: View Results

```bash
python3 scripts/parse_baseline_results.py results/baseline_performance
```

This shows:
- Throughput for each core count
- Latency metrics
- Protocol phase breakdowns (time spent in validation, commit, etc.)

---

## That's It! 🎉

The test runs automatically and saves everything to `results/baseline_performance/`

---

## Optional: Customize Test

### Test only specific cores (e.g., 1, 2, 4, 8):
```bash
CORE_COUNTS="1 2 4 8" ./test_baseline_performance_tpcc.sh
```

### Test all available cores (no 8-core limit):
```bash
TEST_ALL_CORES=1 MAX_CORES=16 ./test_baseline_performance_tpcc.sh
```

---

## Troubleshooting

**"Permission denied"**
```bash
chmod +x test_baseline_performance_tpcc.sh
```

**"Binary not found"**  
Run Step 1 to build.

**"Config file not found"**  
Make sure you're in `/home/ubuntu/mako` directory.


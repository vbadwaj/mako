# 🚀 Quick Start: Build & Test Everything

## One Command to Rule Them All

```bash
cd /home/ubuntu/mako
./build_and_test.sh
```

This will:
1. ✅ Clean build directory
2. ✅ Configure CMake
3. ✅ Build with all cores (`$(nproc)`)
4. ✅ Verify all binaries
5. ✅ Run all unit tests

**Expected time:** 5-10 minutes depending on your system

---

## Manual Step-by-Step (if you prefer)

### 1. Clean & Build

```bash
cd /home/ubuntu/mako
rm -rf build/*
cd build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
make -j$(nproc)
cd ..
```

### 2. Run Tests

```bash
cd build
ctest --output-on-failure -j$(nproc)
cd ..
```

---

## After Build: Run Baseline Performance Test

```bash
./test_baseline_performance_tpcc.sh
```

This tests performance across all core counts (1-8) automatically.

---

## What Each Script Does

- **`build_and_test.sh`**: Complete build + test (recommended)
- **`clean_build.sh`**: Just cleans, you build manually
- **`build_safe.sh`**: Builds only (uses all cores)
- **`test_baseline_performance_tpcc.sh`**: Runs TPC-C baseline performance test

---

## Troubleshooting

**VM crashes during build?**
- Try sequential: `make -j1` instead of `make -j$(nproc)`

**Tests fail?**
- Check test output in `/tmp/mako_ctest.log`
- Try running individual tests: `cd build && ctest -R test_name`

**Binary not found?**
- Check if build completed: `ls build/dbtest` or `ls build/benchmarks/dbtest`


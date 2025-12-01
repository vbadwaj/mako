# Performance Counters Enabled

## Status: ✅ Performance Counters Working

Performance counters (`USE_PERF_CTRS`) have been successfully enabled in the Mako build system.

### What Was Done

1. **Enabled USE_PERF_CTRS in CMakeLists.txt**
   - Added `option(ENABLE_PERF_CTRS "Enable performance counters (scopedperf)" ON)`
   - Added compile definition `-DUSE_PERF_CTRS` when enabled

2. **Fixed Build Issues**
   - Added `#include "base_txn_btree.h"` to `txn_impl.h` to resolve probe reference issues
   - Successfully rebuilt with performance counters enabled

3. **Rebuilt and Re-ran Tests**
   - All baseline performance tests completed with performance counters enabled
   - Transaction-level counters are being printed successfully

### Current Results

Performance counters are working and printing transaction-level metrics:

```
--- perf counters (if enabled, for benchmark) ---
TxnPayment:      tsc           
  avg            11947.9       
  total          10881191692   
  count          910718        
TxnNewOrder:     tsc           
  avg            40595.3       
  total          38576049316   
  count          950258        
...
```

### Protocol Phase Probes

The protocol phase probes (`g_txn_commit_probe0_cg`, `g_txn_commit_probe3_cg`, etc.) are:
- ✅ Instrumented in the code (`txn_impl.h`)
- ✅ Using `ANON_REGION` macros correctly
- ⚠️ Not appearing in the perf counters output yet

**Why they might not be appearing:**
- Function-local static perfsum objects created by `ANON_REGION` may need explicit registration
- They might only print if there's data (but commits are happening, so they should have data)
- The perfsum registration might happen after `printall()` is called

**Next Steps (if needed):**
- Check if probes need explicit `perfsum()` registration in addition to `ANON_REGION`
- Verify that the static perfsum objects are being registered in the global list
- Consider using named perfsum objects instead of anonymous ones for better visibility

### Baseline Performance Results

All baseline tests completed successfully:

```
Cores    Throughput      Committed    Aborted      Abort Rate  
--------------------------------------------------------------------------------
1        69945.70        2114518      0            0.00        %
2        134877.00       4079634      750          0.02        %
3        194681.00       5888202      1065         0.02        %
4        229148.00       6928250      1292         0.02        %
5        265492.00       8028540      1561         0.02        %
6        306093.00       9263245      1821         0.02        %
7        345545.00       10464726     2078         0.02        %
8        348839.00       10558657     2160         0.02        %
```

### Files Modified

1. `CMakeLists.txt` - Added ENABLE_PERF_CTRS option and compile definition
2. `src/mako/txn_impl.h` - Added include for base_txn_btree.h

### Build Command

To enable performance counters:
```bash
cd build
cmake .. -DENABLE_PERF_CTRS=ON
make -j$(nproc) dbtest
```

Performance counters are now enabled by default in the build configuration.


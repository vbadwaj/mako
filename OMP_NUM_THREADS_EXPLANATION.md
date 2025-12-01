# OMP_NUM_THREADS Explained

## What is OMP_NUM_THREADS?

`OMP_NUM_THREADS` is an **OpenMP environment variable** that controls how many threads OpenMP will use for parallel execution.

---

## In the Context of Batch Validation

### Purpose

`OMP_NUM_THREADS` controls how many threads validate transactions **in parallel** when batch validation is enabled.

### How It Works

1. **OpenMP** is a parallel programming API that allows code to run in parallel across multiple CPU cores
2. When you set `OMP_NUM_THREADS=4`, OpenMP will use 4 threads for parallel regions
3. In batch validation, transactions are validated in parallel using OpenMP's `#pragma omp parallel for`

### Example Usage

```bash
# Set number of parallel validation threads
export OMP_NUM_THREADS=4

# Run benchmark with batch validation
export MAKO_ENABLE_BATCH_VALIDATION=1
build/dbtest --num-threads 8 ...
```

### What Happens

- **Batch size**: 32 transactions (default)
- **OMP_NUM_THREADS**: 4 threads
- **Result**: The 32 transactions are distributed across 4 threads
  - Thread 1 validates transactions 0-7 (~8 transactions)
  - Thread 2 validates transactions 8-15 (~8 transactions)
  - Thread 3 validates transactions 16-23 (~8 transactions)
  - Thread 4 validates transactions 24-31 (~8 transactions)
- All threads run **simultaneously**, making validation faster

---

## Code Implementation

In `src/mako/txn_occ_batch_validation.h`, the parallel validation looks like this:

```cpp
void validate_batch_parallel(ValidationBatch &batch) {
  // ...
  
  // Parallel validation using OpenMP
  #ifdef _OPENMP
  #pragma omp parallel for num_threads(num_validation_threads_) schedule(dynamic, 1)
  #endif
  for (size_t i = 0; i < batch.txns.size(); ++i) {
    // Validate transaction i
    bool valid = ValidateTransactionReadSet(batch.txns[i]);
    batch.results[i] = ValidationResult(...);
  }
}
```

The `num_threads(num_validation_threads_)` tells OpenMP how many threads to use. By default, this is set to `DEFAULT_NUM_VALIDATION_THREADS = 4`.

---

## Relationship to OMP_NUM_THREADS

When OpenMP sees `#pragma omp parallel for`:
1. It checks if `num_threads()` is specified (it is: `num_validation_threads_`)
2. If `num_threads()` is specified, it uses that value (respects the explicit setting)
3. If `num_threads()` is NOT specified, it uses `OMP_NUM_THREADS` environment variable

**In our case:**
- `num_validation_threads_` is explicitly set (default: 4)
- So `OMP_NUM_THREADS` may not directly affect batch validation threads
- However, setting `OMP_NUM_THREADS` is good practice and may be used as a fallback

---

## Typical Values

| CPU Cores | Recommended OMP_NUM_THREADS | Notes |
|-----------|----------------------------|-------|
| 4 cores   | 4                          | Use all cores for validation |
| 8 cores   | 4-8                        | Balance validation vs other work |
| 16+ cores | 4-8                        | Don't need all cores for validation |

### Why Not Use All Cores?

- Other threads are running (client threads, workers, etc.)
- Too many threads can cause overhead from context switching
- 4-8 threads is typically optimal for validation

---

## Example: Performance Impact

### Sequential Validation (OMP_NUM_THREADS=1 or disabled)
```
Transaction 1 → Validate (1ms)
Transaction 2 → Validate (1ms)
Transaction 3 → Validate (1ms)
...
Transaction 32 → Validate (1ms)
Total: 32ms for 32 transactions
```

### Parallel Validation (OMP_NUM_THREADS=4)
```
Thread 1: Transactions 0-7   → Validate (1ms each, parallel)
Thread 2: Transactions 8-15  → Validate (1ms each, parallel)
Thread 3: Transactions 16-23 → Validate (1ms each, parallel)
Thread 4: Transactions 24-31 → Validate (1ms each, parallel)
Total: ~8ms for 32 transactions (4× faster!)
```

---

## Configuration

### Default Behavior

The BatchValidator defaults to `DEFAULT_NUM_VALIDATION_THREADS = 4` threads.

### Setting Environment Variable

```bash
# Set before running benchmark
export OMP_NUM_THREADS=4

# This tells OpenMP to use 4 threads for parallel regions
# Batch validation will use these 4 threads for parallel validation
```

### Best Practices

1. **Set OMP_NUM_THREADS**: Even though batch validation sets `num_threads()` explicitly, setting the environment variable is good practice
2. **Match to CPU cores**: Typically set to number of CPU cores or half
3. **Leave headroom**: Don't use all cores - leave some for other threads

---

## Summary

- **`OMP_NUM_THREADS`**: Environment variable that tells OpenMP how many threads to use
- **Batch validation**: Uses OpenMP to validate transactions in parallel
- **Default**: 4 threads (controlled by `num_validation_threads_` in BatchValidator)
- **Impact**: Parallel validation reduces validation time significantly

**Key Point:** `OMP_NUM_THREADS` controls the number of threads that validate transactions simultaneously, making batch validation much faster than sequential validation.


# --num-threads vs OMP_NUM_THREADS Explained

## Quick Answer

**`--num-threads 8`** = 8 **CLIENT/WORKER THREADS** that execute transactions (run the benchmark workload)

**`OMP_NUM_THREADS=6`** = 6 **VALIDATION THREADS** that validate transactions in parallel (during batch validation)

These are **TOTALLY DIFFERENT** and serve **DIFFERENT PURPOSES**!

---

## Detailed Explanation

### `--num-threads 8` (Client/Worker Threads)

**What it controls:**
- Number of **client worker threads** that execute transactions
- These threads run the benchmark workload (TPC-C transactions)
- Each thread independently generates and executes transactions

**What these threads do:**
1. Generate transactions (e.g., NewOrder, Payment, etc.)
2. Execute transaction logic (read/write operations)
3. Call `commit()` when transaction is done
4. Retry if transaction aborts

**Example:**
```
Thread 1: Execute NewOrder transaction → commit()
Thread 2: Execute Payment transaction → commit()
Thread 3: Execute OrderStatus transaction → commit()
...
Thread 8: Execute StockLevel transaction → commit()
```

All 8 threads run **simultaneously**, generating transactions independently.

**Code location:**
- Set via: `--num-threads 8` command-line argument
- Used in: `src/mako/benchmarks/bench.cc` to create `bench_worker` threads
- Each worker thread independently executes transactions

---

### `OMP_NUM_THREADS=6` (Validation Threads)

**What it controls:**
- Number of **parallel validation threads** used during batch validation
- These threads validate transactions in parallel (inside batch validation)
- Only used when batch validation is enabled

**What these threads do:**
1. Validate transactions in parallel within a batch
2. Check read sets, write sets, version numbers
3. Run simultaneously to speed up validation

**Example (with batch size 32):**
```
Thread 1: Validate transactions 0-5   (6 transactions)
Thread 2: Validate transactions 6-11  (6 transactions)
Thread 3: Validate transactions 12-17 (6 transactions)
Thread 4: Validate transactions 18-23 (6 transactions)
Thread 5: Validate transactions 24-28 (5 transactions)
Thread 6: Validate transactions 29-31 (3 transactions)
```

All 6 threads validate **simultaneously**, making validation faster.

**Code location:**
- Set via: `export OMP_NUM_THREADS=6` environment variable
- Used in: `src/mako/txn_occ_batch_validation.h` in `validate_batch_parallel()`
- Controls OpenMP parallel validation

---

## How They Work Together

### Example: `--num-threads 8` + `OMP_NUM_THREADS=6`

```
┌─────────────────────────────────────────────────────────────┐
│ CLIENT THREADS (--num-threads 8)                            │
├─────────────────────────────────────────────────────────────┤
│ Thread 1: Execute transaction → commit()                    │
│ Thread 2: Execute transaction → commit()                    │
│ Thread 3: Execute transaction → commit()                    │
│ ...                                                          │
│ Thread 8: Execute transaction → commit()                    │
└─────────────────────────────────────────────────────────────┘
                         ↓
            All call commit() simultaneously
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ BATCH VALIDATION (collects transactions into batches)       │
├─────────────────────────────────────────────────────────────┤
│ Batch of 32 transactions ready                              │
└─────────────────────────────────────────────────────────────┘
                         ↓
            validate_batch_parallel()
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ VALIDATION THREADS (OMP_NUM_THREADS=6)                      │
├─────────────────────────────────────────────────────────────┤
│ Thread 1: Validate transactions 0-5                         │
│ Thread 2: Validate transactions 6-11                        │
│ Thread 3: Validate transactions 12-17                       │
│ Thread 4: Validate transactions 18-23                       │
│ Thread 5: Validate transactions 24-28                       │
│ Thread 6: Validate transactions 29-31                       │
└─────────────────────────────────────────────────────────────┘
                         ↓
            All validate in parallel (faster!)
```

---

## Visual Comparison

```
--num-threads 8          OMP_NUM_THREADS=6
─────────────────       ──────────────────
8 CLIENT threads        6 VALIDATION threads
│                      │
├─ Worker 1            ├─ Validator 1
├─ Worker 2            ├─ Validator 2  
├─ Worker 3            ├─ Validator 3
├─ Worker 4            ├─ Validator 4
├─ Worker 5            ├─ Validator 5
├─ Worker 6            ├─ Validator 6
├─ Worker 7            │
└─ Worker 8            │
                        │
Execute transactions    Validate transactions
Generate workload       Check versions/conflicts
Call commit()           Run during commit()
```

---

## Typical Configuration

### Example Setup

```bash
# 8 client threads generate transactions
--num-threads 8

# 6 threads validate in parallel (within batch validation)
export OMP_NUM_THREADS=6

# Batch validation enabled
export MAKO_ENABLE_BATCH_VALIDATION=1
```

### What Happens

1. **8 client threads** run simultaneously, generating and executing transactions
2. When transactions call `commit()`, they enter **batch validation**
3. Transactions are collected into batches (size 32)
4. When batch is ready, **6 validation threads** validate all 32 transactions in parallel
5. Results returned to client threads, which proceed to write phase

---

## Performance Impact

### `--num-threads` (Client Threads)
- **More threads** = More concurrent transactions = Higher load
- Typical values: 1-16 (depends on CPU cores and workload)
- Too many = contention, too few = underutilization

### `OMP_NUM_THREADS` (Validation Threads)
- **More threads** = Faster batch validation = Lower latency
- Typical values: 4-8 (enough for parallel validation)
- Too many = diminishing returns, overhead

---

## Summary

| Parameter | Controls | Purpose | When Used |
|-----------|----------|---------|-----------|
| `--num-threads 8` | Client worker threads | Execute transactions (benchmark workload) | Always (benchmark execution) |
| `OMP_NUM_THREADS=6` | Validation threads | Validate transactions in parallel | Only when batch validation enabled |

**They work together:**
- Client threads (`--num-threads`) generate transactions and call `commit()`
- Validation threads (`OMP_NUM_THREADS`) validate those transactions faster in parallel

**Key Point:** These are **different layers**:
- `--num-threads`: Application-level parallelism (more transactions)
- `OMP_NUM_THREADS`: Validation-level parallelism (faster validation)


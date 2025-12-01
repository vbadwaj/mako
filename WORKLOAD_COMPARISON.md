# Workload Comparison: TPC-C vs Synthetic Workloads

## Overview

For baseline performance profiling, we have two main options:

1. **TPC-C**: Industry-standard complex OLTP benchmark
2. **Synthetic Workloads**: Simpler, more controllable workloads

## Option 1: TPC-C (Transaction Processing Performance Council - C)

### What It Is
- **Industry-standard OLTP benchmark** simulating an e-commerce warehouse management system
- **5 transaction types**: NewOrder, Payment, Delivery, OrderStatus, StockLevel
- **Multiple tables**: Warehouses, Districts, Customers, Items, Orders, OrderLines, Stock, etc.
- **Complex relationships**: Foreign keys, multi-table joins, scans

### Characteristics

**Complexity:**
- ✅ **Realistic**: Mimics real-world database workloads
- ✅ **Well-established**: Standard benchmark used in research
- ✅ **Multi-table**: Tests complex transaction logic
- ❌ **Complex**: Hard to understand what's happening
- ❌ **Setup overhead**: Requires data loading, configuration

**Transaction Profile:**
- **Mixed read/write**: ~50% reads, ~50% writes
- **Variable read set sizes**: 5-50+ tuples per transaction
- **Variable write set sizes**: 1-15+ tuples per transaction
- **Contention**: Natural hotspots (popular items, recent orders)

**Code Location:**
- `src/mako/benchmarks/tpcc.cc` (full implementation)
- `src/mako/benchmarks/tpcc_simple.cc` (simplified version)

### Example Transaction (NewOrder)
```cpp
// Reads: warehouse, district, customer, item (multiple)
// Writes: new_order, order, order_line (multiple), stock updates
// Scans: order_line table
```

### Pros
- ✅ **Industry standard** - Results comparable to published papers
- ✅ **Realistic** - Represents real OLTP workloads
- ✅ **Already integrated** - Works with Mako out of the box
- ✅ **Contention patterns** - Natural conflict scenarios
- ✅ **Comprehensive** - Tests many aspects of the system

### Cons
- ❌ **Complex setup** - Requires configuration files, data loading
- ❌ **Harder to debug** - Many moving parts
- ❌ **Less control** - Can't easily control read/write set sizes
- ❌ **Slower iteration** - More time to run and analyze
- ❌ **Overhead** - Transaction logic overhead may obscure protocol overhead

---

## Option 2: Synthetic Simple Workload

### What It Is
- **Controlled key-value operations** on a single table
- **Configurable**: Control read/write ratios, set sizes, contention
- **Minimal overhead**: Just read/write operations, no business logic

### Characteristics

**Simplicity:**
- ✅ **Easy to understand**: Clear, simple operations
- ✅ **Controllable**: Easy to adjust parameters
- ✅ **Fast iteration**: Quick to run and analyze
- ✅ **Minimal overhead**: Focuses on protocol performance
- ❌ **Less realistic**: Doesn't represent real applications

**Transaction Profile:**
- **Configurable read/write ratio**: e.g., 50% reads, 50% writes
- **Fixed read set size**: e.g., always 5 tuples
- **Fixed write set size**: e.g., always 2 tuples
- **Controllable contention**: Can adjust hotspot probability

**Code Location:**
- `src/mako/benchmarks/ut/simpleTransaction.cc` (unit test example)
- Could create new: `src/mako/benchmarks/synthetic_kv.cc`

### Example Transaction (Simple Read-Write)
```cpp
// Transaction:
// 1. Read 5 random keys
// 2. Write 2 random keys (possibly overlapping)
// 3. Commit
```

### Pros
- ✅ **Simple** - Easy to understand and debug
- ✅ **Fast** - Quick to run, fast iteration
- ✅ **Controllable** - Precise control over workload characteristics
- ✅ **Isolated** - Focuses on protocol performance, not application logic
- ✅ **Reproducible** - Easy to reproduce exact conditions

### Cons
- ❌ **Not standard** - Results less comparable to research papers
- ❌ **Less realistic** - Doesn't test complex scenarios
- ❌ **May miss issues** - Simpler workload may not expose all problems

---

## Comparison Table

| Aspect | TPC-C | Synthetic Simple |
|--------|-------|------------------|
| **Complexity** | High (multiple tables, complex logic) | Low (single table, simple ops) |
| **Realism** | ✅ High (real-world patterns) | ❌ Low (artificial) |
| **Setup Time** | ❌ Long (data loading, config) | ✅ Short (minimal config) |
| **Debugging** | ❌ Hard (many components) | ✅ Easy (simple flow) |
| **Control** | ❌ Limited (fixed transaction mix) | ✅ High (configurable) |
| **Iteration Speed** | ❌ Slow (longer runs) | ✅ Fast (quick runs) |
| **Industry Standard** | ✅ Yes (widely used) | ❌ No (custom) |
| **Protocol Focus** | ❌ Mixed with app logic | ✅ Pure protocol |
| **Read/Write Set Sizes** | ❌ Variable | ✅ Configurable fixed |
| **Contention Control** | ❌ Natural (hard to control) | ✅ Precise control |

---

## Recommendation for Baseline Performance Profiling

### **Start with Synthetic Simple Workload** ✅

**Why:**
1. **Focus on protocol**: We want to measure **validation performance**, not application logic overhead
2. **Controllable**: Easy to test different read/write set sizes systematically
3. **Fast iteration**: Can quickly test many configurations
4. **Clear results**: Protocol overhead will be clearly visible

**Then validate with TPC-C:**
- After establishing baseline with synthetic workload
- To show improvements work on realistic workloads
- To publish comparable results

### Proposed Synthetic Workload

Create a new benchmark: `synthetic_perf.cc`

**Parameters:**
- `--num-keys`: Total keyspace size (e.g., 1,000,000)
- `--read-set-size`: Number of keys to read per transaction (e.g., 5)
- `--write-set-size`: Number of keys to write per transaction (e.g., 2)
- `--read-ratio`: Percentage of read-only transactions (e.g., 0.5 = 50%)
- `--hotspot-ratio`: Percentage of operations hitting hotspot (e.g., 0.1 = 10%)
- `--hotspot-size`: Number of keys in hotspot (e.g., 100)

**Transaction Types:**
1. **Read-only**: Read N keys, commit
2. **Write-only**: Write N keys, commit  
3. **Read-write**: Read M keys, write N keys, commit

**Workload Pattern:**
```cpp
// Simple transaction pattern
void synthetic_txn() {
  void *txn = db->new_txn(...);
  
  // Read phase
  for (int i = 0; i < read_set_size; i++) {
    key = select_random_key();
    table->get(txn, key, value);
  }
  
  // Write phase
  for (int i = 0; i < write_set_size; i++) {
    key = select_random_key();
    table->put(txn, key, new_value);
  }
  
  db->commit_txn(txn);
}
```

---

## Implementation Strategy

### Phase 1: Synthetic Baseline (Recommended Starting Point)
1. Create `synthetic_perf.cc` benchmark
2. Run baseline tests with 1, 2, 4, 8 cores
3. Profile protocol phases
4. Document baseline performance

### Phase 2: TPC-C Validation (Optional, Later)
1. Run same tests with TPC-C
2. Compare results
3. Show improvements on realistic workload

---

## Summary

**For baseline performance profiling:**
- ✅ **Use synthetic simple workload** for initial profiling
  - Focuses on protocol performance
  - Fast, controllable, easy to debug
  - Clear separation of protocol overhead

- ⚠️ **Consider TPC-C later** for validation
  - More realistic but complex
  - Good for final validation and publications

The synthetic workload will give us **clean, interpretable results** about validation performance without application logic overhead confusing the measurements.


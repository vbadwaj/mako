# How OCC is Implemented in Mako

Mako implements **Optimistic Concurrency Control (OCC)** as part of its speculative 2PC protocol. Unlike traditional OCC systems, Mako's validation is integrated into its native transaction protocol.

## Core OCC Concepts in Mako

### 1. **Version-Based Validation**

Each database tuple (`dbtuple`) maintains:
- **`version`** field: A transaction ID (TID) that identifies when the tuple was last modified
- **`hdr`** field: A bit-packed header containing version information and locks

```cpp
// From src/mako/tuple.h
struct dbtuple {
  volatile version_t hdr;  // Bit-packed: [locked|deleting|write_intent|modifying|latest|version]
  tid_t version;           // Transaction ID of last modification
  // ...
};
```

### 2. **Transaction Sets**

During transaction execution, Mako tracks:
- **Read Set**: Tuples that were read, along with their versions at read time
- **Write Set**: Tuples that will be modified
- **Absent Set**: B-tree nodes scanned to check for non-existence

```cpp
// From src/mako/txn.h
read_set_map read_set;      // Maps tuples to their read versions
write_set_map write_set;    // Tuples to be written
absent_set_map absent_set;  // B-tree versions for scan validation
```

### 3. **OCC Validation at Commit Time**

The validation happens in `transaction::commit()` in `src/mako/txn_impl.h`:

#### **Step 1: Version Checking**

For each tuple in the **read set**, check if its version has changed since it was read:

```cpp
// Lines 396-421 in txn_impl.h
if (!read_set.empty()) {
  for (auto it = read_set.begin(); it != read_set.end(); ++it) {
    // Check if tuple is also in write set (we wrote to it, so version is OK)
    bool found = sorted_dbtuples_contains(write_dbtuples, it->get_tuple());
    
    // Validate version hasn't changed
    if (found ?
        it->get_tuple()->is_latest_version(it->get_tid()) :
        it->get_tuple()->stable_is_latest_version(it->get_tid()))
      continue;  // Version is still valid
    
    // Version changed - ABORT
    abort_trap((reason = ABORT_REASON_READ_NODE_INTEREFERENCE));
    goto do_abort;
  }
}
```

**Key Methods:**
- `is_latest_version(tid)`: Checks if tuple is at the latest version for the given TID
- `stable_is_latest_version(tid)`: Waits for any in-progress modifications, then checks version
- `reader_check_version(version)`: Validates that the version header hasn't changed

#### **Step 2: B-tree Version Checking**

For scans that checked for non-existence, validate B-tree node versions haven't changed:

```cpp
// Lines 423-436 in txn_impl.h
if (!absent_set.empty()) {
  for (auto it = absent_set.begin(); it != absent_set.end(); ++it) {
    const uint64_t v = concurrent_btree::ExtractVersionNumber(it->first);
    if (unlikely(v != it->second.version)) {
      // B-tree node structure changed - ABORT
      abort_trap((reason = ABORT_REASON_NODE_SCAN_READ_VERSION_CHANGED));
      goto do_abort;
    }
  }
}
```

### 4. **Version Checking Methods**

#### **Reader Version Check** (from `src/mako/tuple.h:556-564`)

```cpp
inline bool reader_check_version(version_t version) const {
  COMPILER_MEMORY_FENCE;
  // Check if versions match, ignoring lock/write_intent/latest bits
  const version_t MODULO_BITS =
    (HDR_LOCKED_MASK | HDR_WRITE_INTENT_MASK | HDR_LATEST_MASK);
  return (hdr & ~MODULO_BITS) == (version & ~MODULO_BITS);
}
```

This checks if the version number itself hasn't changed, ignoring transient lock states.

#### **Writer Version Check** (from `src/mako/tuple.h:567-571`)

```cpp
inline bool writer_check_version(version_t version) const {
  COMPILER_MEMORY_FENCE;
  return hdr == version;  // Exact match including all flags
}
```

More strict - requires exact match including lock states.

#### **Stable Version Reading** (from `src/mako/tuple.h:509-528`)

```cpp
inline version_t reader_stable_version(bool allow_write_intent) const {
  version_t v = hdr;
  // Wait until tuple is not being modified
  while (IsModifying(v) || (!allow_write_intent && IsWriteIntent(v))) {
    nop_pause();  // Spin-wait
    v = hdr;
  }
  COMPILER_MEMORY_FENCE;
  return v;
}
```

Waits for any in-progress writes before reading the version.

### 5. **Parallel Batch Validation (Our Enhancement)**

We added parallel validation to improve performance by batching multiple transactions and validating them concurrently:

```cpp
// From src/mako/txn_occ_batch_validation.h
bool ValidateTransactionReadSet(txn_type *txn) {
  // Extract write tuples
  dbtuple_write_info_vec write_dbtuples;
  // ... build write_dbtuples ...
  
  // Validate read set (same logic as sequential validation)
  for (auto it = txn->read_set.begin(); it != txn->read_set.end(); ++it) {
    bool found = /* check if in write set */;
    
    if (likely(found ?
          it->get_tuple()->is_latest_version(it->get_tid()) :
          it->get_tuple()->stable_is_latest_version(it->get_tid())))
      continue;
    
    return false;  // Validation failed
  }
  
  return true;  // Validation passed
}
```

This validation runs in parallel across multiple transactions using OpenMP.

## OCC Flow Diagram

```
Transaction Execution:
┌─────────────────────┐
│  Transaction Start  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Read Operations    │───┐
│  - Track read_set   │   │ Record versions
│  - Store TID        │◄──┘
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Write Operations   │───┐
│  - Track write_set  │   │ Prepare writes
│  - Lock tuples      │◄──┘
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  commit() called    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  VALIDATION PHASE   │
│  (OCC Check)        │
│                     │
│  1. For each read:  │
│     - Check version │
│     - Still valid?  │──┐
│                     │  │
│  2. For each scan:  │  │
│     - Check B-tree  │  │
│       version       │  │
│                     │  │
│  All valid? ────────┼──┤
└──────────┬──────────┘  │
           │             │
     ┌─────┴─────┐       │
     │           │       │
     ▼           ▼       │
┌─────────┐ ┌──────────┐│
│  ABORT  │ │  COMMIT  ││
│         │ │          ││
│ Release │ │  Install ││
│ locks   │ │  writes  ││
└─────────┘ └──────────┘│
                        │
                        │
┌───────────────────────┴───────┐
│  If parallel batch enabled:   │
│  - Batch multiple transactions│
│  - Validate in parallel       │
│  - Reduce serialization       │
└───────────────────────────────┘
```

## Key Differences from Classic OCC

1. **Integrated with 2PC**: Mako's OCC is part of a speculative two-phase commit protocol, not standalone
2. **Version is TID**: Versions are transaction IDs, not simple counters
3. **Locking for Writes**: Write operations acquire locks (optimistic for reads, pessimistic for writes)
4. **B-tree Versioning**: Also tracks B-tree structure versions for scan validation

## Why Validation is Critical

If validation fails, it means:
- Another transaction modified a tuple we read
- The B-tree structure changed during a scan
- Our read view is no longer consistent

In these cases, the transaction **must abort** to maintain serializability.

## Performance Considerations

1. **Sequential Validation**: Original implementation validates transactions one-by-one (serialization bottleneck)
2. **Parallel Batch Validation**: Our enhancement batches transactions and validates them concurrently
3. **Fast Path**: If a tuple is in both read and write sets, we already have a lock, so validation is simpler

## References

- Core validation logic: `src/mako/txn_impl.h:396-436`
- Tuple version checking: `src/mako/tuple.h:556-571`
- Parallel batch validation: `src/mako/txn_occ_batch_validation.h`
- Transaction data structures: `src/mako/txn.h`

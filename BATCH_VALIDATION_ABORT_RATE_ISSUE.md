# Batch Validation Abort Rate Issue

## Current Status
- **Baseline abort rate**: 71.4%
- **Batch validation abort rate**: 72-73%
- **Target**: 30-40% (40-60% reduction)
- **Batch validation counters**: ALL ZERO (batch validation not running!)

## Root Cause Analysis

### Problem 1: Batch Validation Not Running
- Batch validation counters (`batch_validations`, `batch_validated_txns`, `batch_aborted_txns`) are all 0
- This means batch validation is not actually being invoked
- Possible reasons:
  1. Transactions are snapshots (which skip batch validation)
  2. Batch validation code path not being executed
  3. Environment variable not being read correctly

### Problem 2: High Abort Rates Even If Batch Validation Works
- Baseline abort rate is already very high (71.4%)
- Batch validation alone won't reduce abort rates - need smarter conflict resolution
- Current conflict detection is too aggressive (simple "first wins" strategy)
- Conflicts still occur at write phase (lock acquisition) even after validation

## Solutions Needed

### Immediate: Fix Batch Validation Invocation
1. Verify transactions are not snapshots (or handle snapshots differently)
2. Add debug logging to trace batch validation invocation
3. Ensure environment variables are read correctly

### Short-term: Improve Conflict Detection
1. Current conflict detection is too aggressive - aborting too many transactions
2. Need dependency graph analysis to find valid serialization orders
3. Only abort when truly necessary (bidirectional conflicts)

### Long-term: Coordinate Write Phase
1. Transactions validated together still compete for locks independently
2. Need to coordinate lock acquisition for batch-validated transactions
3. OR ensure all conflicts resolved before write phase begins

## Next Steps
1. Debug why batch validation counters are 0
2. Add smarter conflict resolution using dependency graphs
3. Coordinate write phase for batch-validated transactions
4. Test and verify abort rate reduction to 30-40%

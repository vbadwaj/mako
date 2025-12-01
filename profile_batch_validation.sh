#!/bin/bash
# Profile batch validation with gperftools

set -e

echo "=== Profiling Batch Validation ==="

# Set profiling environment variable
export CPUPROFILE=./batch_validation.prof
export CPUPROFILESIGNAL=12

# Enable batch validation
export MAKO_ENABLE_BATCH_VALIDATION=1
export MAKO_BATCH_VALIDATION_SIZE=32
export MAKO_BATCH_VALIDATION_MAX_WAIT_US=1000

echo "Profiling batch validation run..."
echo "CPU profile will be written to: $CPUPROFILE"
echo ""

# Run dbtest with profiling
timeout 30s taskset -c 0-7 build/dbtest \
  --site-name local_s0 \
  --shard-config config/local-tpcc-baseline.yml \
  --num-threads 8 \
  2>&1 | tee batch_validation_profile.log

echo ""
echo "=== Profiling Complete ==="
echo "Profile saved to: $CPUPROFILE"
echo ""
echo "To view profile:"
echo "  google-pprof build/dbtest $CPUPROFILE"
echo "  OR"
echo "  ./scripts/pprof build/dbtest $CPUPROFILE"

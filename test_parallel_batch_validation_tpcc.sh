#!/bin/bash

# Parallel Batch Validation Performance Test using TPC-C
# Tests performance with parallel batch validation enabled across different core counts
# This is the "parallel" version - compares against baseline (sequential validation)

set -e

# Configuration
BUILD_DIR="build"
DURATION=30
RESULTS_DIR="results/parallel_batch_validation"
# Try both possible locations
if [ -f "${BUILD_DIR}/dbtest" ]; then
    BINARY="${BUILD_DIR}/dbtest"
elif [ -f "${BUILD_DIR}/benchmarks/dbtest" ]; then
    BINARY="${BUILD_DIR}/benchmarks/dbtest"
else
    echo "Error: dbtest binary not found in ${BUILD_DIR}/dbtest or ${BUILD_DIR}/benchmarks/dbtest"
    exit 1
fi
# Use local TPC-C baseline config
if [ -f "config/local-tpcc-baseline.yml" ]; then
    CONFIG_FILE="config/local-tpcc-baseline.yml"
elif [ -f "config/mako_single_node.yml" ]; then
    CONFIG_FILE="config/mako_single_node.yml"
else
    echo "ERROR: No suitable config file found"
    exit 1
fi

# Batch validation configuration
BATCH_SIZE=${MAKO_BATCH_VALIDATION_SIZE:-32}
MAX_WAIT_US=${MAKO_BATCH_VALIDATION_MAX_WAIT_US:-1000}

# Auto-detect available cores
TOTAL_CORES=$(nproc)
PHYSICAL_CORES=$(lscpu -p | grep -v '^#' | cut -d',' -f2 | sort -u | wc -l)

# Determine which core counts to test
# Option 1: Set CORE_COUNTS env var to override (e.g., CORE_COUNTS="1 2 4 8")
# Option 2: Set TEST_ALL_CORES=1 to test all cores from 1 to TOTAL_CORES
# Option 3: Default behavior - test all cores from 1 to TOTAL_CORES (up to 8)

if [ -n "$CORE_COUNTS" ]; then
    # Use explicitly provided list
    IFS=', ' read -r -a CORE_COUNTS <<< "$CORE_COUNTS"
elif [ "${TEST_ALL_CORES:-1}" = "1" ]; then
    # Auto-test ALL cores from 1 to available cores (default behavior)
    MAX_TEST=$((TOTAL_CORES < 8 ? TOTAL_CORES : 8))  # Cap at 8 for reasonable test time
    CORE_COUNTS=($(seq 1 $MAX_TEST))
else
    # Fallback: test powers of 2
    CORE_COUNTS=(1 2 4 8)
fi

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "TPC-C Parallel Batch Validation Test"
echo "=========================================="
echo ""

# Check if binary exists
if [ ! -f "$BINARY" ]; then
    echo "ERROR: Binary not found at $BINARY"
    echo "Please build Mako first with batch validation enabled:"
    echo "  cd build"
    echo "  cmake .. -DENABLE_BATCH_VALIDATION=ON -DENABLE_OPENMP=ON"
    echo "  make -j\$(nproc)"
    exit 1
fi

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Create results directory
mkdir -p "$RESULTS_DIR"

# Enable batch validation for parallel testing
export MAKO_ENABLE_BATCH_VALIDATION=1
export MAKO_BATCH_VALIDATION_SIZE=$BATCH_SIZE
export MAKO_BATCH_VALIDATION_MAX_WAIT_US=$MAX_WAIT_US

echo "Parallel Batch Validation Configuration:"
echo "  Batch validation: ENABLED"
echo "  Batch size: $BATCH_SIZE"
echo "  Max wait time: $MAX_WAIT_US microseconds"
echo "  Duration: $DURATION seconds per test"
echo "  Binary: $BINARY"
echo "  Config: $CONFIG_FILE"
echo ""
echo "System Information:"
echo "  Total cores available: $TOTAL_CORES"
echo "  Physical cores: $PHYSICAL_CORES"
echo ""
echo "Testing core counts: ${CORE_COUNTS[*]}"
MAX_CORE_TO_TEST=${CORE_COUNTS[${#CORE_COUNTS[@]}-1]}
echo "  (Auto-testing all cores from 1 to $MAX_CORE_TO_TEST)"
echo "  (Override with: CORE_COUNTS='1 2 4' ./test_parallel_batch_validation_tpcc.sh)"
echo ""
echo "=========================================="
echo ""

# Function to get CPU frequency for normalization
get_cpu_freq() {
    if [ -f /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq ]; then
        cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
    else
        echo "unknown"
    fi
}

CPU_FREQ=$(get_cpu_freq)
echo "CPU Frequency: $CPU_FREQ kHz"
echo ""

# Function to run test with specific core count
run_test() {
    local cores=$1
    local output_file="$RESULTS_DIR/parallel_${cores}cores.log"
    local json_file="$RESULTS_DIR/parallel_${cores}cores.json"
    
    echo -e "${BLUE}Testing with $cores core(s) (Parallel Batch Validation)...${NC}"
    
    # Build taskset mask for cores 0 to (cores-1)
    local mask="0"
    if [ $cores -gt 1 ]; then
        for ((i=1; i<cores; i++)); do
            mask="$mask,$i"
        done
    fi
    
    echo "  Core mask: $mask"
    echo "  Pinning to cores: 0-$((cores-1))"
    
    # Prepare environment - batch validation is already enabled above
    export MAKO_ENABLE_PERFORMANCE_PROFILING="1"
    
    # Run with core pinning using taskset
    echo "  Starting benchmark..."
    
    START_TIME=$(date +%s.%N)
    
    # Run benchmark - dbtest runs until killed, so we use timeout command
    # Use --site-name to specify we're running as the leader (single node mode)
    timeout $((DURATION + 120)) taskset -c $mask \
        "$BINARY" \
        --site-name local_s0 \
        --num-threads $cores \
        --shard-config "$CONFIG_FILE" \
        --shard-index 0 \
        > "$output_file" 2>&1 || {
        EXIT_CODE=$?
        if [ $EXIT_CODE -eq 124 ]; then
            echo -e "${YELLOW}  Benchmark timed out after ${DURATION}s${NC}"
        else
            echo -e "${YELLOW}  Warning: Benchmark exited with code $EXIT_CODE${NC}"
        fi
    }
    
    END_TIME=$(date +%s.%N)
    ACTUAL_DURATION=$(echo "$END_TIME - $START_TIME" | bc)
    
    echo "  Completed in ${ACTUAL_DURATION}s"
    echo ""
    
    # Extract metrics from output
    if [ -f "$output_file" ]; then
        # Extract throughput
        THROUGHPUT=$(grep -i "throughput" "$output_file" | grep -oE "[0-9]+\.?[0-9]*" | head -1 || echo "0")
        
        # Extract commit/abort counts - look for n_commits and calculate aborts from abort_rate
        COMMITS=$(grep "^n_commits:" "$output_file" 2>/dev/null | tail -1 | awk '{print $2}' || echo "0")
        
        # Calculate aborts from abort_rate * runtime
        ABORT_RATE=$(grep "agg_abort_rate:" "$output_file" 2>/dev/null | awk '{print $2}' || echo "0")
        RUNTIME=$(grep "^runtime:" "$output_file" 2>/dev/null | awk '{print $2}' || echo "0")
        if [ "$ABORT_RATE" != "0" ] && [ "$RUNTIME" != "0" ]; then
            ABORTS=$(echo "$ABORT_RATE * $RUNTIME" | bc 2>/dev/null | cut -d. -f1 || echo "0")
        else
            ABORTS="0"
        fi
        
        # Extract batch validation stats if available
        BATCH_VALIDATIONS=$(grep "g_evt_batch_validations:" "$output_file" 2>/dev/null | awk '{print $2}' || echo "0")
        BATCH_VALIDATED_TXNS=$(grep "g_evt_batch_validated_txns:" "$output_file" 2>/dev/null | awk '{print $2}' || echo "0")
        BATCH_ABORTED_TXNS=$(grep "g_evt_batch_aborted_txns:" "$output_file" 2>/dev/null | awk '{print $2}' || echo "0")
        AVG_BATCH_SIZE=$(grep "g_evt_avg_batch_size:" "$output_file" 2>/dev/null | awk '{print $2}' || echo "0")
        
        # Extract performance counter stats if available
        echo "  Extracting performance metrics..."
        
        # Create JSON summary
        cat > "$json_file" <<EOF
{
  "core_count": $cores,
  "duration_seconds": $DURATION,
  "actual_duration": $ACTUAL_DURATION,
  "cpu_frequency_khz": "$CPU_FREQ",
  "throughput": {
    "txns_per_second": $THROUGHPUT,
    "committed": $COMMITS,
    "aborted": $ABORTS
  },
  "configuration": {
    "batch_validation": true,
    "batch_size": $BATCH_SIZE,
    "max_wait_us": $MAX_WAIT_US,
    "workload": "tpcc",
    "scale_factor": $cores
  },
  "batch_validation_stats": {
    "batch_validations": $BATCH_VALIDATIONS,
    "batch_validated_txns": $BATCH_VALIDATED_TXNS,
    "batch_aborted_txns": $BATCH_ABORTED_TXNS,
    "avg_batch_size": $AVG_BATCH_SIZE
  },
  "output_file": "$output_file"
}
EOF
        
        echo -e "${GREEN}  ✓ Results saved to: $json_file${NC}"
    else
        echo -e "${YELLOW}  Warning: Output file not created${NC}"
    fi
    
    echo ""
}

# Run tests for each core count
echo "=========================================="
echo "Running Parallel Batch Validation Tests"
echo "=========================================="
echo ""

for cores in "${CORE_COUNTS[@]}"; do
    run_test $cores
    
    # Small delay between tests
    sleep 2
done

# Summary
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "Results saved to: $RESULTS_DIR/"
echo ""
echo "Individual results:"
for cores in "${CORE_COUNTS[@]}"; do
    json_file="$RESULTS_DIR/parallel_${cores}cores.json"
    if [ -f "$json_file" ]; then
        echo "  $cores cores: $json_file"
    fi
done
echo ""
echo "To view detailed logs:"
echo "  cat $RESULTS_DIR/parallel_*cores.log"
echo ""
echo "To compare with baseline:"
echo "  python3 scripts/compare_baseline_parallel.py"
echo ""


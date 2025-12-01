#!/bin/bash
# Complete build and test script using all available cores

set -e

echo "=========================================="
echo "Mako Build & Test Script"
echo "=========================================="
echo ""

CORES=$(nproc)
echo "Detected $CORES CPU cores"
echo ""

# Step 1: Clean
echo "Step 1: Cleaning build directory..."
cd "$(dirname "$0")"
rm -rf build/*
echo "✓ Cleaned"
echo ""

# Step 2: Configure
echo "Step 2: Configuring CMake..."
cd build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
echo "✓ Configured"
echo ""

# Step 3: Build
echo "Step 3: Building with $CORES parallel jobs..."
make -j$(nproc)
echo "✓ Build complete!"
echo ""

# Step 4: Check binaries
echo "Step 4: Verifying key binaries..."
BINARIES=("dbtest" "simpleTransaction" "simplePaxos")
MISSING=0

for bin in "${BINARIES[@]}"; do
    if [ -f "$bin" ]; then
        echo "  ✓ $bin found"
    elif [ -f "benchmarks/$bin" ]; then
        echo "  ✓ benchmarks/$bin found"
    else
        echo "  ✗ $bin NOT FOUND"
        MISSING=1
    fi
done

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "WARNING: Some binaries are missing!"
    echo "Build may have failed partially."
    exit 1
fi

echo ""
echo "Step 5: Running tests..."
echo ""

# Run unit tests
cd ..
echo "Running unit tests (ctest)..."
cd build
if ctest --output-on-failure -j$(nproc) 2>&1 | tee /tmp/mako_ctest.log; then
    echo ""
    echo "✓ Unit tests passed!"
else
    echo ""
    echo "✗ Some unit tests failed. Check /tmp/mako_ctest.log"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ All builds and tests completed!"
echo "=========================================="
echo ""
echo "Key binaries:"
find build -name "dbtest" -o -name "simpleTransaction" -o -name "simplePaxos" 2>/dev/null | head -5
echo ""
echo "Next steps:"
echo "  Run baseline test: ./test_baseline_performance_tpcc.sh"


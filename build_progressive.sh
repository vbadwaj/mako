#!/bin/bash
# Progressive build - tries increasing parallelism until it works

set -e

cd "$(dirname "$0")/build"

echo "Configuring CMake..."
cmake .. -DENABLE_BATCH_VALIDATION=OFF

echo ""
echo "Attempting progressive build (will try safer options first)..."
echo ""

# Try progressively more parallelism
for jobs in 2 4 8; do
    echo "Trying: make -j$jobs"
    if timeout 300 make -j$jobs 2>&1; then
        echo ""
        echo "✓ Build successful with -j$jobs!"
        break
    else
        if [ $? -eq 124 ]; then
            echo "Build timed out or crashed with -j$jobs"
        else
            echo "Build failed with -j$jobs, trying next option..."
        fi
        if [ $jobs -eq 8 ]; then
            echo ""
            echo "All parallel builds failed. Trying sequential build (-j1)..."
            make -j1
            echo "✓ Build successful with sequential build!"
        fi
    fi
done

echo ""
echo "Build complete!"
echo "Binary location: $(find . -name dbtest -type f 2>/dev/null | head -1)"


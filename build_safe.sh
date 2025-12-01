#!/bin/bash
# Build script using all available cores

set -e

cd "$(dirname "$0")/build"

echo "Configuring CMake..."
cmake .. -DENABLE_BATCH_VALIDATION=OFF

CORES=$(nproc)
echo "Building with $CORES parallel jobs..."
make -j$(nproc)

echo "✓ Build complete!"
echo "Binary location: $(find . -name dbtest -type f 2>/dev/null | head -1)"


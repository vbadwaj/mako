#!/bin/bash
# Clean build script - removes all build artifacts for fresh rebuild

set -e

BUILD_DIR="build"

echo "Cleaning build directory..."

# Option 1: Remove everything in build/ (keeps the directory)
if [ -d "$BUILD_DIR" ]; then
    echo "Removing all files in $BUILD_DIR/..."
    rm -rf "$BUILD_DIR"/*
    echo "✓ Cleaned build directory"
else
    echo "Build directory doesn't exist, creating it..."
    mkdir -p "$BUILD_DIR"
fi

echo ""
echo "Ready for fresh build! Run:"
echo "  cd build && cmake .. && make -j\$(nproc)"
echo ""
echo "Or use the build script:"
echo "  ./build_safe.sh"


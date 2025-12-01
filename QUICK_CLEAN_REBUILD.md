# Quick Clean & Rebuild Guide

## Option 1: Use the Clean Script (Easiest)

```bash
cd /home/ubuntu/mako
./clean_build.sh
cd build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
make -j2
cd ..
```

---

## Option 2: Manual Clean (Full Control)

### Step 1: Clean build artifacts

```bash
cd /home/ubuntu/mako/build
make clean
```

**OR for complete clean (removes everything):**

```bash
cd /home/ubuntu/mako
rm -rf build/*
```

---

### Step 2: Rebuild from scratch

```bash
cd /home/ubuntu/mako/build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
make -j2
```

---

## Option 3: Nuclear Option (Cleanest)

**Removes entire build directory and recreates:**

```bash
cd /home/ubuntu/mako
rm -rf build
mkdir build
cd build
cmake .. -DENABLE_BATCH_VALIDATION=OFF
make -j2
cd ..
```

---

## What Each Does

- **`make clean`**: Removes compiled objects but keeps CMake config
- **`rm -rf build/*`**: Removes everything in build/, but keeps directory
- **`rm -rf build`**: Complete removal, need to recreate directory

**Recommendation**: Use Option 1 (the script) for simplicity!


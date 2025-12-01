#pragma once

#include <atomic>

namespace mako {

struct BatchValidationStats {
  std::atomic<uint64_t> num_batches{0};
  std::atomic<uint64_t> num_txns_in_batches{0};
  std::atomic<uint64_t> num_batch_committed{0};
  std::atomic<uint64_t> num_batch_aborted{0};

  void reset() {
    num_batches.store(0, std::memory_order_relaxed);
    num_txns_in_batches.store(0, std::memory_order_relaxed);
    num_batch_committed.store(0, std::memory_order_relaxed);
    num_batch_aborted.store(0, std::memory_order_relaxed);
  }
};

inline BatchValidationStats& GetBatchValidationStats() {
  static BatchValidationStats stats;
  return stats;
}

}  // namespace mako



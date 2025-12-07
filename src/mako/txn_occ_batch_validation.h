#ifndef _NDB_TXN_OCC_BATCH_VALIDATION_H_
#define _NDB_TXN_OCC_BATCH_VALIDATION_H_

#include <vector>
#include <atomic>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <memory>
#include <unordered_set>
#include <chrono>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cctype>
#ifdef _OPENMP
#include <omp.h>
#endif
#include "occ_reorder/txn_batch_metadata.h"
#include "occ_reorder/txn_reorder_controller.h"
#include "txn.h"
#include "occ_reorder/batch_validation_counters.h"
#include "occ_reorder/batch_validation_trace.h"
#include "macros.h"
#include "thread.h"
#include "core.h"
#include "counter.h"
#include "tuple.h"
#include "masstree_btree.h"

namespace mako {

/**
 * Parallel Batch Validator for OCC transactions
 *
 * Batches multiple transactions and validates them in parallel to improve
 * throughput under contention. This reduces the serialization bottleneck
 * of sequential validation.
 *
 * Design:
 * - Transactions ready to commit are batched together
 * - Batch validation runs in parallel across multiple threads
 * - Only transactions that pass validation proceed to write phase
 * - Failed transactions abort and retry
 */
template <template <typename> class Protocol, typename Traits>
class BatchValidator {
public:
  typedef transaction<Protocol, Traits> txn_type;
  
  // Configuration
  static const size_t DEFAULT_BATCH_SIZE = 32;
  static const size_t DEFAULT_MAX_WAIT_US = 1000;  // 1ms max wait to fill batch
  static const size_t DEFAULT_NUM_VALIDATION_THREADS = 4;

  struct ValidationResult {
    txn_type *txn;
    bool valid;
    typename transaction_base::abort_reason reason;
    
    ValidationResult() : txn(nullptr), valid(false), reason(transaction_base::ABORT_REASON_NONE) {}
    ValidationResult(txn_type *t, bool v, typename transaction_base::abort_reason r)
      : txn(t), valid(v), reason(r) {}
  };

private:
  // Batch of transactions pending validation
  struct ValidationBatch {
    std::vector<txn_type*> txns;
    std::vector<ValidationResult> results;
    bool is_full() const { return txns.size() >= batch_size_; }
    
    size_t batch_size_;
    
    ValidationBatch(size_t bs) : batch_size_(bs) {
      txns.reserve(bs);
      results.reserve(bs);
    }
    
    void reset() {
      txns.clear();
      results.clear();
    }
  };

  // Per-transaction entry for worker thread pattern
  struct BatchEntry {
    txn_type *txn;
    size_t position_in_batch;
    bool validated{false};
    bool valid_result{false};
    std::mutex mutex;
    std::condition_variable cv;
    std::atomic<bool> enqueued{false};  // For non-blocking enqueue
    
    BatchEntry(txn_type *t) : txn(t), position_in_batch(0) {}
  };

  // Configuration
  size_t batch_size_;
  size_t max_wait_us_;
  size_t num_validation_threads_;
  bool enabled_;
  bool txn_reorder_enabled_{false};
  bool pre_validation_enabled_{true};  // Pre-validation enabled by default

  // Worker thread pattern for batch collection (eliminates mutex contention)
  std::mutex batch_mutex_;
  std::vector<BatchEntry*> pending_entries_;
  std::condition_variable batch_cv_;
  std::atomic<bool> shutdown_{false};
  std::thread worker_thread_;
  bool worker_running_{false};
  std::chrono::steady_clock::time_point first_enqueue_time_;
  
  // Statistics (using function-local statics to avoid template static member issues)
  static event_counter& get_batch_validations_counter() {
    return occ::batch_validations_counter();
  }
  static event_counter& get_batch_validated_txns_counter() {
    return occ::batch_validated_txns_counter();
  }
  static event_counter& get_batch_aborted_txns_counter() {
    return occ::batch_aborted_txns_counter();
  }
  static event_avg_counter& get_avg_batch_size_counter() {
    return occ::avg_batch_size_counter();
  }
  static event_avg_counter& get_avg_batch_validation_time_counter() {
    return occ::avg_batch_validation_time_counter();
  }
  static event_counter& get_txn_reorder_attempts_counter() {
    return occ::txn_reorder_attempts_counter();
  }
  static event_counter& get_txn_reorder_applied_counter() {
    return occ::txn_reorder_applied_counter();
  }
  static event_counter& get_txn_reorder_removed_counter() {
    return occ::txn_reorder_removed_counter();
  }
  static event_counter& get_txn_reorder_cycles_counter() {
    return occ::txn_reorder_cycles_counter();
  }

  static void EnsureCounterReporterRegistered();
  static void ReportCountersAtExit();
  static void PrintCounter(const char* name);

public:
  BatchValidator()
    : batch_size_(DEFAULT_BATCH_SIZE),
      max_wait_us_(DEFAULT_MAX_WAIT_US),
      num_validation_threads_(DEFAULT_NUM_VALIDATION_THREADS),
      enabled_(false),
      worker_running_(false) {
    (void) get_batch_validations_counter();
    (void) get_batch_validated_txns_counter();
    (void) get_batch_aborted_txns_counter();
    (void) get_avg_batch_size_counter();
    (void) get_avg_batch_validation_time_counter();
    (void) get_txn_reorder_attempts_counter();
    (void) get_txn_reorder_applied_counter();
    (void) get_txn_reorder_removed_counter();
    (void) get_txn_reorder_cycles_counter();
  }

  ~BatchValidator() {
    shutdown();
    if (worker_thread_.joinable()) {
      worker_thread_.join();
    }
    ReportCountersAtExit();
  }

  /**
   * Initialize the batch validator with configuration
   */
  void Init(size_t batch_size = DEFAULT_BATCH_SIZE,
            size_t max_wait_us = DEFAULT_MAX_WAIT_US,
            size_t num_threads = DEFAULT_NUM_VALIDATION_THREADS) {
    batch_size_ = batch_size;
    max_wait_us_ = max_wait_us;

    // Derive validation thread count:
    // 1) MAKO_BATCH_VALIDATION_THREADS (explicit override)
    // 2) OMP_NUM_THREADS if OpenMP is enabled
    // 3) Fallback to num_threads argument (usually DEFAULT_NUM_VALIDATION_THREADS)
    size_t threads = num_threads;
    if (const char* env = std::getenv("MAKO_BATCH_VALIDATION_THREADS")) {
      char* end = nullptr;
      unsigned long v = std::strtoul(env, &end, 10);
      if (end != env && v > 0) {
        threads = static_cast<size_t>(v);
      }
    }
#ifdef _OPENMP
    if (threads == 0) {
      if (const char* omp_env = std::getenv("OMP_NUM_THREADS")) {
        char* end = nullptr;
        unsigned long v = std::strtoul(omp_env, &end, 10);
        if (end != omp_env && v > 0) {
          threads = static_cast<size_t>(v);
        }
      }
    }
#endif
    if (threads == 0) {
      threads = DEFAULT_NUM_VALIDATION_THREADS;
    }
    // Avoid spawning more validation threads than there are txns in a batch
    threads = std::max<size_t>(1, std::min(threads, batch_size_));
    num_validation_threads_ = threads;
    enabled_ = true;
    EnsureCounterReporterRegistered();
    const char* reorder_env = std::getenv("MAKO_ENABLE_TXN_REORDER");
    if (reorder_env) {
      std::string flag(reorder_env);
      txn_reorder_enabled_ = (flag == "1" || flag == "true" || flag == "TRUE");
    }
    
    // Pre-validation is enabled by default when reordering is enabled
    // Can be disabled via environment variable
    const char* pre_val_env = std::getenv("MAKO_DISABLE_PRE_VALIDATION");
    if (pre_val_env) {
      std::string flag(pre_val_env);
      pre_validation_enabled_ = !(flag == "1" || flag == "true" || flag == "TRUE");
    } else {
      pre_validation_enabled_ = txn_reorder_enabled_;  // Enable if reordering is enabled
    }
    
    // Start worker thread for batch collection
    if (!worker_running_) {
      shutdown_.store(false);
      pending_entries_.clear();
      worker_running_ = true;
      first_enqueue_time_ = std::chrono::steady_clock::now();
      worker_thread_ = std::thread([this]() { WorkerLoop(); });
    }
  }

  /**
   * Shutdown the batch validator
   */
  void shutdown() {
    if (!enabled_ || !worker_running_)
      return;
      
    shutdown_.store(true);
    batch_cv_.notify_all();
    enabled_ = false;
    
    if (worker_thread_.joinable()) {
      worker_thread_.join();
    }
    worker_running_ = false;
  }

  /**
   * Add transaction to batch for parallel validation (non-blocking)
   * Enqueues transaction and returns immediately. Use WaitForValidation to wait.
   * 
   * @param txn Transaction to add to batch
   * @return Pointer to BatchEntry if enqueued, nullptr if batch disabled or snapshot
   */
  BatchEntry* EnqueueToBatch(txn_type *txn) {
    if (!enabled_ || txn->is_snapshot()) {
      // Snapshots don't need validation or batching disabled
      return nullptr;
    }
    
    // Create entry for this transaction (allocated on heap for async access)
    BatchEntry* entry = new BatchEntry(txn);
    
    // Enqueue to worker thread (minimal lock scope)
    {
      std::lock_guard<std::mutex> lock(batch_mutex_);
      if (shutdown_.load()) {
        delete entry;
        return nullptr;
      }
      if (pending_entries_.empty()) {
        first_enqueue_time_ = std::chrono::steady_clock::now();
      }
      pending_entries_.push_back(entry);
      entry->enqueued.store(true);
      batch_cv_.notify_one();
    }
    
    return entry;
  }

  /**
   * Wait for transaction validation to complete
   * 
   * @param entry BatchEntry returned from EnqueueToBatch
   * @return true if validation passed, false if failed
   */
  bool WaitForValidation(BatchEntry* entry) {
    if (!entry) {
      return false;
    }
    
    // Wait for validation result from worker thread
    std::unique_lock<std::mutex> entry_lock(entry->mutex);
    entry->cv.wait(entry_lock, [entry]() { return entry->validated; });
    
    bool result = entry->valid_result;
    delete entry;  // Clean up entry
    return result;
  }

  /**
   * Add transaction to batch for parallel validation (blocking, for backward compatibility)
   * Blocks until batch is validated and returns validation result
   * 
   * @param txn Transaction to add to batch
   * @return true if transaction was validated in batch (check txn->state for result), 
   *         false if should validate immediately (batch disabled or snapshot)
   */
  bool AddToBatch(txn_type *txn) {
    // Check if pipelining is enabled
    const char* pipeline_env = std::getenv("MAKO_ENABLE_TXN_PIPELINING");
    bool pipelining_enabled = (pipeline_env && (std::string(pipeline_env) == "1" || std::string(pipeline_env) == "true"));
    
    if (pipelining_enabled) {
      // Non-blocking enqueue for pipelining
      BatchEntry* entry = EnqueueToBatch(txn);
      if (!entry) {
        return false;
      }
      // Store entry in thread-local queue for later waiting
      GetThreadLocalEntryQueue().push_back(entry);
      // Don't wait yet - return immediately
      // Worker loop will wait for all entries together
      return true;  // Indicates enqueued, validation pending
    } else {
      // Blocking mode (original behavior)
      BatchEntry* entry = EnqueueToBatch(txn);
      if (!entry) {
        return false;
      }
      return WaitForValidation(entry);
    }
  }

  /**
   * Wait for all pending validations in thread-local queue
   * Returns true if all validations passed, false if any failed
   */
  bool WaitForAllPendingValidations() {
    auto& queue = GetThreadLocalEntryQueue();
    if (queue.empty()) {
      return true;
    }
    
    bool all_passed = true;
    for (BatchEntry* entry : queue) {
      if (entry) {
        bool passed = WaitForValidation(entry);
        all_passed = all_passed && passed;
      }
    }
    queue.clear();
    return all_passed;
  }

private:
  /**
   * Get thread-local queue of batch entries for pipelining
   */
  static std::vector<BatchEntry*>& GetThreadLocalEntryQueue() {
    thread_local static std::vector<BatchEntry*> entry_queue;
    return entry_queue;
  }

  /**
   * Worker thread loop that collects batches and validates them
   * This eliminates mutex contention by having a single thread collect batches
   */
  void WorkerLoop() {
    std::vector<BatchEntry*> ready;
    
    while (true) {
      {
        std::unique_lock<std::mutex> lock(batch_mutex_);
        
        // Wait for transactions or shutdown
        batch_cv_.wait(lock, [this]() {
          return shutdown_.load() || !pending_entries_.empty();
        });
        
        if (shutdown_.load() && pending_entries_.empty()) {
          break;
        }
        
        if (pending_entries_.empty()) {
          continue;
        }
        
        const size_t pending_size = pending_entries_.size();
        bool flush_now = pending_size >= batch_size_;
        bool timed_out = false;
        
        if (!flush_now) {
          const auto deadline = first_enqueue_time_ + 
                                std::chrono::microseconds(max_wait_us_);
          const bool predicate = batch_cv_.wait_until(lock, deadline, [this]() {
            return shutdown_.load() || pending_entries_.size() >= batch_size_;
          });
          timed_out = !predicate;
        }
        
        if (shutdown_.load() && pending_entries_.empty()) {
          break;
        }
        
        const bool should_flush = flush_now || timed_out || shutdown_.load();
        if (!should_flush) {
          continue;
        }
        
        // Move pending entries to ready batch
        ready.swap(pending_entries_);
        const size_t batch_size = ready.size();
        const auto wait_duration = std::chrono::steady_clock::now() - first_enqueue_time_;
        const auto wait_us = std::chrono::duration_cast<std::chrono::microseconds>(wait_duration).count();
        const char* reason = flush_now ? "FULL" : (timed_out ? "TIMEOUT" : "SHUTDOWN");
        
        if (BatchValidationTraceEnabled()) {
          std::fprintf(stderr,
                       "[batch_validation] flush size=%zu queue_size_after=0 wait_us=%ld reason=%s\n",
                       batch_size,
                       wait_us,
                       reason);
        }
        
        pending_entries_.clear();
        first_enqueue_time_ = std::chrono::steady_clock::now();
      }
      
      // Process batch outside of lock
      if (!ready.empty()) {
        ProcessBatch(ready);
        ready.clear();
      }
    }
    
    // Notify any remaining entries on shutdown
    std::lock_guard<std::mutex> lock(batch_mutex_);
    for (BatchEntry* entry : pending_entries_) {
      if (entry) {
        std::lock_guard<std::mutex> entry_lock(entry->mutex);
        entry->validated = true;
        entry->valid_result = false; // Abort on shutdown
        entry->cv.notify_one();
      }
    }
    // Clean up entries (they will be deleted by WaitForValidation or here on shutdown)
    for (BatchEntry* entry : pending_entries_) {
      if (entry) {
        delete entry;
      }
    }
    pending_entries_.clear();
  }
  
  /**
   * Process a batch of transactions: validate and notify waiting threads
   */
  void ProcessBatch(std::vector<BatchEntry*>& entries) {
    if (entries.empty()) {
      return;
    }
    
    // Build ValidationBatch from entries
    ValidationBatch batch(batch_size_);
    for (size_t i = 0; i < entries.size(); ++i) {
      entries[i]->position_in_batch = i;
      batch.txns.push_back(entries[i]->txn);
    }
    
    // Log batch size for debugging
    static std::atomic<size_t> total_batches{0};
    static std::atomic<size_t> total_txns{0};
    static size_t max_batch_seen{0};
    total_batches.fetch_add(1);
    total_txns.fetch_add(batch.txns.size());
    if (batch.txns.size() > max_batch_seen) {
      max_batch_seen = batch.txns.size();
    }
    // Print stats every 100 batches
    if (total_batches.load() % 100 == 0) {
      size_t batches = total_batches.load();
      size_t txns = total_txns.load();
      double avg_batch = batches > 0 ? static_cast<double>(txns) / static_cast<double>(batches) : 0.0;
      std::fprintf(stderr, "[BATCH_STATS] batches=%zu total_txns=%zu avg_batch_size=%.2f max_batch_size=%zu\n",
                   batches, txns, avg_batch, max_batch_seen);
    }
    
    // Validate batch in parallel
    validate_batch_parallel(batch);
    
    // Notify all waiting transactions
    for (size_t i = 0; i < entries.size() && i < batch.results.size(); ++i) {
      BatchEntry* entry = entries[i];
      std::lock_guard<std::mutex> entry_lock(entry->mutex);
      entry->valid_result = batch.results[i].valid;
      entry->validated = true;
      entry->cv.notify_one();
    }
  }

  /**
   * Validate a single transaction's read set
   * This is called in parallel by validation threads
   */
  static bool ValidateTransactionReadSet(txn_type *txn) {
    INVARIANT(txn != nullptr);
    
    // Extract read set and write tuples (similar to commit logic)
    typename txn_type::dbtuple_write_info_vec write_dbtuples;
    
    // Copy write tuples (if any) for conflict checking
    if (!txn->write_set.empty()) {
      typename txn_type::write_set_map::iterator it = txn->write_set.begin();
      typename txn_type::write_set_map::iterator it_end = txn->write_set.end();
      for (size_t pos = 0; it != it_end; ++it, ++pos) {
        write_dbtuples.emplace_back(it->get_tuple(), &(*it), it->is_insert(), pos);
      }
    }
    
    // Validate read set (same logic as txn_impl.h:343-368)
    if (!txn->read_set.empty()) {
      typename txn_type::read_set_map::iterator it = txn->read_set.begin();
      typename txn_type::read_set_map::iterator it_end = txn->read_set.end();
      for (; it != it_end; ++it) {
        // Check if tuple is in write set
        bool found = false;
        const dbtuple *read_tuple = it->get_tuple();
        for (const auto &w : write_dbtuples) {
          if (w.tuple.get() == read_tuple) {
            found = true;
            break;
          }
        }
        
        // Check if version is still valid
        if (likely(found ?
              it->get_tuple()->is_latest_version(it->get_tid()) :
              it->get_tuple()->stable_is_latest_version(it->get_tid())))
          continue;
        
        // Validation failed - version changed
        return false;
      }
    }
    
    // Validate absent set (btree versions)
    if (!txn->absent_set.empty()) {
      typename txn_type::absent_set_map::iterator it = txn->absent_set.begin();
      typename txn_type::absent_set_map::iterator it_end = txn->absent_set.end();
      for (; it != it_end; ++it) {
        const uint64_t v = concurrent_btree::ExtractVersionNumber(it->first);
        if (unlikely(v != it->second.version)) {
          return false;
        }
      }
    }
    
    return true;
  }

private:
  /**
   * Validate a batch of transactions in parallel
   * Uses OpenMP or std::execution::par for parallel validation
   */
  void validate_batch_parallel(ValidationBatch &batch) {
    if (batch.txns.empty())
      return;
    
    get_batch_validations_counter().inc();
    get_avg_batch_size_counter().offer(batch.txns.size());
    
    auto start_time = std::chrono::high_resolution_clock::now();
    batch.results.clear();
    if (BatchValidationTraceEnabled()) {
      std::fprintf(stderr,
                   "[batch_validation] validating batch size=%zu reorder=%s\n",
                   batch.txns.size(),
                   txn_reorder_enabled_ ? "on" : "off");
    }

    // Pre-validation: filter non-viable transactions before expensive reordering
    std::vector<txn_type*> viable_txns;
    std::unordered_map<txn_type*, bool> pre_validation_results;
    
    if (pre_validation_enabled_ && txn_reorder_enabled_) {
      viable_txns.reserve(batch.txns.size());
      pre_validation_results.reserve(batch.txns.size());
      
      // Pre-validate all transactions in parallel
      #ifdef _OPENMP
      #pragma omp parallel for num_threads(num_validation_threads_) schedule(dynamic, 1)
      #endif
      for (size_t i = 0; i < batch.txns.size(); ++i) {
        bool valid = ValidateTransactionReadSet(batch.txns[i]);
        #ifdef _OPENMP
        #pragma omp critical
        #endif
        {
          pre_validation_results[batch.txns[i]] = valid;
          if (valid) {
            viable_txns.push_back(batch.txns[i]);
          }
        }
      }
      
      if (BatchValidationTraceEnabled()) {
        std::fprintf(stderr,
                     "[pre_validation] filtered batch: %zu -> %zu viable transactions\n",
                     batch.txns.size(),
                     viable_txns.size());
      }
    } else {
      // No pre-validation: all transactions are considered viable
      viable_txns = batch.txns;
      for (txn_type* txn : batch.txns) {
        pre_validation_results[txn] = true;
      }
    }

    if (txn_reorder_enabled_ && !viable_txns.empty()) {
      get_txn_reorder_attempts_counter().inc();
      auto plan = occ::TxnReorderController<Protocol, Traits>::Plan(viable_txns);
      if (plan.cycle_components > 0) {
        get_txn_reorder_cycles_counter().inc(plan.cycle_components);
      }
      if (plan.removed_nodes > 0) {
        get_txn_reorder_removed_counter().inc(plan.removed_nodes);
      }
      if (plan.applied) {
        get_txn_reorder_applied_counter().inc();
        if (BatchValidationTraceEnabled()) {
          std::fprintf(stderr,
                       "[txn_reorder] plan graph_nodes=%zu edges=%zu removed=%zu "
                       "cycle_components=%zu applied=1\n",
                       plan.graph_nodes,
                       plan.graph_edges,
                       plan.removed_nodes,
                       plan.cycle_components);
        }
        // Initialize results map for all transactions
        std::unordered_map<uint64_t, size_t> index_map;
        batch.results.assign(batch.txns.size(), ValidationResult());
        for (size_t i = 0; i < batch.txns.size(); ++i) {
          batch.results[i].txn = batch.txns[i];
          index_map.emplace(reinterpret_cast<uint64_t>(batch.txns[i]), i);
          
          // Mark transactions that failed pre-validation as aborted
          if (!pre_validation_results[batch.txns[i]]) {
            batch.results[i] = ValidationResult(
                batch.txns[i], false, transaction_base::ABORT_REASON_READ_NODE_INTEREFERENCE);
            batch.txns[i]->state = transaction_base::TXN_ABRT;
            batch.txns[i]->reason = transaction_base::ABORT_REASON_READ_NODE_INTEREFERENCE;
            get_batch_aborted_txns_counter().inc();
          }
        }

        auto place_result = [&](txn_type* txn,
                                bool valid,
                                transaction_base::abort_reason reason) {
          auto it =
              index_map.find(reinterpret_cast<uint64_t>(txn));
          if (it == index_map.end()) {
            return;
          }
          batch.results[it->second] = ValidationResult(txn, valid, reason);
        };

        for (auto* txn : plan.aborted) {
          place_result(txn, false, transaction_base::ABORT_REASON_USER);
          txn->state = transaction_base::TXN_ABRT;
          txn->reason = transaction_base::ABORT_REASON_USER;
          get_batch_aborted_txns_counter().inc();
        }

        // Final validation: validate reordered transactions against current database state
        for (auto* txn : plan.ordered) {
          // Final validation (second validation pass after reordering)
          bool valid = ValidateTransactionReadSet(txn);
          auto reason = valid ? transaction_base::ABORT_REASON_NONE
                              : transaction_base::ABORT_REASON_READ_NODE_INTEREFERENCE;
          place_result(txn, valid, reason);
          if (valid) {
            get_batch_validated_txns_counter().inc();
          } else {
            txn->state = transaction_base::TXN_ABRT;
            txn->reason = reason;
            get_batch_aborted_txns_counter().inc();
          }
        }

        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration_us = std::chrono::duration_cast<std::chrono::microseconds>(
            end_time - start_time)
                               .count();
        get_avg_batch_validation_time_counter().offer(duration_us);
        return;
      }
      if (BatchValidationTraceEnabled()) {
        std::fprintf(stderr,
                     "[txn_reorder] plan graph_nodes=%zu edges=%zu removed=%zu "
                     "cycle_components=%zu applied=0\n",
                     plan.graph_nodes,
                     plan.graph_edges,
                     plan.removed_nodes,
                     plan.cycle_components);
      }
    }

    batch.results.resize(batch.txns.size());
    
    // Parallel validation: distribute across threads
    // OpenMP parallel for is a blocking construct, so no need for busy-wait
    #ifdef _OPENMP
    #pragma omp parallel for num_threads(num_validation_threads_) schedule(dynamic, 1)
    #endif
    for (size_t i = 0; i < batch.txns.size(); ++i) {
      txn_type *txn = batch.txns[i];
      
      // Validate this transaction
      bool valid = ValidateTransactionReadSet(txn);
      
      batch.results[i] = ValidationResult(
        txn,
        valid,
        valid ? transaction_base::ABORT_REASON_NONE : 
                transaction_base::ABORT_REASON_READ_NODE_INTEREFERENCE);
    }
    
    // OpenMP parallel for blocks until all iterations complete, so validated_count
    // is no longer needed. Removed busy-wait loop for better performance.
    
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration_us = std::chrono::duration_cast<std::chrono::microseconds>(
      end_time - start_time).count();
    get_avg_batch_validation_time_counter().offer(duration_us);
    
    // Process results - mark transactions as validated
    for (size_t i = 0; i < batch.results.size(); ++i) {
      if (batch.results[i].valid) {
        get_batch_validated_txns_counter().inc();
      } else {
        get_batch_aborted_txns_counter().inc();
        batch.txns[i]->state = transaction_base::TXN_ABRT;
        batch.txns[i]->reason = batch.results[i].reason;
      }
    }
  }

};

template <template <typename> class Protocol, typename Traits>
void BatchValidator<Protocol, Traits>::EnsureCounterReporterRegistered() {
#ifdef ENABLE_EVENT_COUNTERS
  static std::once_flag register_once;
  std::call_once(register_once, []() {
    std::atexit(&BatchValidator::ReportCountersAtExit);
  });
#endif
}

template <template <typename> class Protocol, typename Traits>
void BatchValidator<Protocol, Traits>::ReportCountersAtExit() {
#ifdef ENABLE_EVENT_COUNTERS
  static std::once_flag emit_once;
  std::call_once(emit_once, []() {
    std::fprintf(stderr, "--- batch_validation_counters ---\n");
    PrintCounter("batch_validations");
    PrintCounter("batch_validated_txns");
    PrintCounter("batch_aborted_txns");
    PrintCounter("avg_batch_size");
    PrintCounter("avg_batch_validation_time_us");
    std::fprintf(stderr, "--- txn_reorder_counters ---\n");
    PrintCounter("txn_reorder_attempts");
    PrintCounter("txn_reorder_applied");
    PrintCounter("txn_reorder_removed_txns");
    PrintCounter("txn_reorder_cycles_detected");
  });
#endif
}

template <template <typename> class Protocol, typename Traits>
void BatchValidator<Protocol, Traits>::PrintCounter(const char* name) {
#ifdef ENABLE_EVENT_COUNTERS
  counter_data data;
  if (!event_counter::stat(name, data)) {
    return;
  }
  if (data.type_ == counter_data::TYPE_COUNT) {
    std::fprintf(stderr,
                 "%s: count=%llu\n",
                 name,
                 static_cast<unsigned long long>(data.count_));
  } else {
    const double avg =
        data.count_ ? static_cast<double>(data.sum_) / static_cast<double>(data.count_) : 0.0;
    std::fprintf(stderr,
                 "%s: count=%llu, max=%llu, avg=%.2f\n",
                 name,
                 static_cast<unsigned long long>(data.count_),
                 static_cast<unsigned long long>(data.max_),
                 avg);
  }
#else
  (void) name;
#endif
}

} // namespace mako

// Global singleton instance for batch validator
// Access via GetBatchValidator() function
template <template <typename> class Protocol, typename Traits>
inline mako::BatchValidator<Protocol, Traits>&
GetBatchValidator() {
  static mako::BatchValidator<Protocol, Traits> g_batch_validator;
  return g_batch_validator;
}

// Helper function to wait for all pending validations (for pipelining)
template <template <typename> class Protocol, typename Traits>
inline bool
WaitForAllPendingBatchValidations() {
  auto& validator = GetBatchValidator<Protocol, Traits>();
  return validator.WaitForAllPendingValidations();
}

#endif /* _NDB_TXN_OCC_BATCH_VALIDATION_H_ */


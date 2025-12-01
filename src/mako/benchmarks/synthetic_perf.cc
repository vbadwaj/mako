/**
 * Synthetic Performance Benchmark for Baseline Profiling
 * 
 * Purpose: Measure baseline transaction performance with configurable workload
 * to profile time spent in different protocol phases.
 * 
 * Features:
 * - Configurable read/write set sizes
 * - Controllable contention
 * - Core pinning support
 * - Performance metrics collection
 */

#include <iostream>
#include <iomanip>
#include <thread>
#include <vector>
#include <atomic>
#include <chrono>
#include <random>
#include <sstream>
#include <getopt.h>
#include <sched.h>
#include <unistd.h>

#include "bench.h"
#include "mbta_wrapper.hh"
#include "../counter.h"
#include "../scopedperf.hh"
#include "benchmark_config.h"
#include "lib/configuration.h"

using namespace std;
using namespace util;

// Global statistics
atomic<uint64_t> committed_txns{0};
atomic<uint64_t> aborted_txns{0};
atomic<bool> stop_flag{false};
atomic<uint64_t> total_reads{0};
atomic<uint64_t> total_writes{0};

// Configuration
struct BenchmarkConfig {
    int num_threads = 4;
    int duration_sec = 30;
    int num_keys = 100000;
    int read_set_size = 5;
    int write_set_size = 2;
    double read_only_ratio = 0.0;  // 0.0 = all read-write, 1.0 = all read-only
    double hotspot_ratio = 0.1;    // 10% of operations hit hotspot
    int hotspot_size = 100;        // 100 keys in hotspot
    int pin_cores = 0;             // 0 = don't pin, 1 = pin threads
    bool enable_profiling = true;
};

BenchmarkConfig bench_config;

class SyntheticWorker {
public:
    SyntheticWorker(abstract_db *db, int worker_id, mt19937 &rng) 
        : db(db), worker_id(worker_id), rng(rng) {
        txn_obj_buf.reserve(str_arena::MinStrReserveLength);
        txn_obj_buf.resize(db->sizeof_txn_object(0));
    }

    void initialize() {
        scoped_db_thread_ctx ctx(db, false);
        TThread::enable_multiverison();
        table = db->open_index("synthetic_table");
        
        // Pin to core if requested
        if (bench_config.pin_cores) {
            cpu_set_t cpuset;
            CPU_ZERO(&cpuset);
            int core_id = worker_id % sysconf(_SC_NPROCESSORS_ONLN);
            CPU_SET(core_id, &cpuset);
            if (pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset) != 0) {
                cerr << "Warning: Failed to pin thread " << worker_id << " to core " << core_id << endl;
            }
        }
    }

    void run() {
        scoped_db_thread_ctx ctx(db, false);
        
        auto start_time = chrono::high_resolution_clock::now();
        auto end_time = start_time + chrono::seconds(bench_config.duration_sec);
        
        uniform_real_distribution<double> read_dist(0.0, 1.0);
        uniform_int_distribution<int> key_dist(0, bench_config.num_keys - 1);
        uniform_int_distribution<int> hotspot_dist(0, bench_config.hotspot_size - 1);
        uniform_real_distribution<double> hotspot_prob_dist(0.0, 1.0);
        
        while (chrono::high_resolution_clock::now() < end_time && !stop_flag.load()) {
            void *txn = db->new_txn(0, arena, txn_buf());
            scoped_str_arena s_arena(arena);
            
            try {
                // Decide transaction type
                bool is_read_only = read_dist(rng) < bench_config.read_only_ratio;
                
                // Read phase
                int reads_this_txn = 0;
                if (!is_read_only || bench_config.read_set_size > 0) {
                    for (int i = 0; i < bench_config.read_set_size; i++) {
                        string key = generate_key(key_dist, hotspot_dist, hotspot_prob_dist, rng);
                        string value;
                        table->get(txn, key, value);
                        reads_this_txn++;
                    }
                }
                
                // Write phase
                int writes_this_txn = 0;
                if (!is_read_only && bench_config.write_set_size > 0) {
                    for (int i = 0; i < bench_config.write_set_size; i++) {
                        string key = generate_key(key_dist, hotspot_dist, hotspot_prob_dist, rng);
                        string value = mako::Encode("value_" + to_string(worker_id) + "_" + 
                                                   to_string(committed_txns.load()));
                        table->put(txn, key, value);
                        writes_this_txn++;
                    }
                }
                
                db->commit_txn(txn);
                committed_txns.fetch_add(1, memory_order_relaxed);
                total_reads.fetch_add(reads_this_txn, memory_order_relaxed);
                total_writes.fetch_add(writes_this_txn, memory_order_relaxed);
            } catch (abstract_db::abstract_abort_exception &ex) {
                db->abort_txn(txn);
                aborted_txns.fetch_add(1, memory_order_relaxed);
            }
        }
    }

private:
    string generate_key(uniform_int_distribution<int> &key_dist,
                       uniform_int_distribution<int> &hotspot_dist,
                       uniform_real_distribution<double> &hotspot_prob_dist,
                       mt19937 &rng) {
        // Generate key with hotspot support
        int key_id;
        if (hotspot_prob_dist(rng) < bench_config.hotspot_ratio) {
            // Hit hotspot
            key_id = hotspot_dist(rng);
        } else {
            // Random key from full keyspace
            key_id = key_dist(rng);
        }
        return "key_" + to_string(key_id);
    }

    abstract_db *const db;
    int worker_id;
    mt19937 &rng;
    str_arena arena;
    string txn_obj_buf;
    abstract_ordered_index *table;
    inline void *txn_buf() { return (void *)txn_obj_buf.data(); }
};

class DataLoader {
public:
    DataLoader(abstract_db *db, int num_keys) : db(db), num_keys(num_keys) {
        txn_obj_buf.reserve(str_arena::MinStrReserveLength);
        txn_obj_buf.resize(db->sizeof_txn_object(0));
    }

    void load() {
        scoped_db_thread_ctx ctx(db, true);
        table = db->open_index("synthetic_table");
        
        // Load initial data in batches
        const int batch_size = 1000;
        for (int i = 0; i < num_keys; i += batch_size) {
            void *txn = db->new_txn(0, arena, txn_buf());
            scoped_str_arena s_arena(arena);
            
            try {
                int end = min(i + batch_size, num_keys);
                for (int j = i; j < end; j++) {
                    string key = "key_" + to_string(j);
                    string value = mako::Encode("initial_value_" + to_string(j));
                    table->put(txn, key, value);
                }
                db->commit_txn(txn);
            } catch (abstract_db::abstract_abort_exception &ex) {
                db->abort_txn(txn);
                i -= batch_size; // Retry batch
            }
        }
        
        cout << "Loaded " << num_keys << " keys" << endl;
    }

private:
    abstract_db *const db;
    int num_keys;
    str_arena arena;
    string txn_obj_buf;
    abstract_ordered_index *table;
    inline void *txn_buf() { return (void *)txn_obj_buf.data(); }
};

void print_usage(const char *prog) {
    cerr << "Usage: " << prog << " [options]" << endl;
    cerr << "Options:" << endl;
    cerr << "  -t, --threads N          Number of threads (default: 4)" << endl;
    cerr << "  -d, --duration N         Duration in seconds (default: 30)" << endl;
    cerr << "  -k, --keys N             Number of keys (default: 100000)" << endl;
    cerr << "  -r, --read-set-size N    Read set size (default: 5)" << endl;
    cerr << "  -w, --write-set-size N   Write set size (default: 2)" << endl;
    cerr << "  --read-only-ratio F      Ratio of read-only txns (default: 0.0)" << endl;
    cerr << "  --hotspot-ratio F        Ratio of hotspot operations (default: 0.1)" << endl;
    cerr << "  --hotspot-size N         Hotspot size in keys (default: 100)" << endl;
    cerr << "  --pin-cores              Pin threads to cores" << endl;
    cerr << "  -h, --help               Show this help" << endl;
}

void parse_args(int argc, char **argv) {
    static struct option long_options[] = {
        {"threads", required_argument, 0, 't'},
        {"duration", required_argument, 0, 'd'},
        {"keys", required_argument, 0, 'k'},
        {"read-set-size", required_argument, 0, 'r'},
        {"write-set-size", required_argument, 0, 'w'},
        {"read-only-ratio", required_argument, 0, 1},
        {"hotspot-ratio", required_argument, 0, 2},
        {"hotspot-size", required_argument, 0, 3},
        {"pin-cores", no_argument, 0, 4},
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0}
    };

    int c;
    while ((c = getopt_long(argc, argv, "t:d:k:r:w:h", long_options, nullptr)) != -1) {
        switch (c) {
        case 't':
            bench_config.num_threads = atoi(optarg);
            break;
        case 'd':
            bench_config.duration_sec = atoi(optarg);
            break;
        case 'k':
            bench_config.num_keys = atoi(optarg);
            break;
        case 'r':
            bench_config.read_set_size = atoi(optarg);
            break;
        case 'w':
            bench_config.write_set_size = atoi(optarg);
            break;
        case 1:
            bench_config.read_only_ratio = atof(optarg);
            break;
        case 2:
            bench_config.hotspot_ratio = atof(optarg);
            break;
        case 3:
            bench_config.hotspot_size = atoi(optarg);
            break;
        case 4:
            bench_config.pin_cores = 1;
            break;
        case 'h':
            print_usage(argv[0]);
            exit(0);
        default:
            print_usage(argv[0]);
            exit(1);
        }
    }
}

void print_config() {
    cout << "==========================================" << endl;
    cout << "Synthetic Performance Benchmark" << endl;
    cout << "==========================================" << endl;
    cout << "Configuration:" << endl;
    cout << "  Threads:           " << bench_config.num_threads << endl;
    cout << "  Duration:          " << bench_config.duration_sec << " seconds" << endl;
    cout << "  Keyspace size:     " << bench_config.num_keys << endl;
    cout << "  Read set size:     " << bench_config.read_set_size << endl;
    cout << "  Write set size:    " << bench_config.write_set_size << endl;
    cout << "  Read-only ratio:   " << (bench_config.read_only_ratio * 100) << "%" << endl;
    cout << "  Hotspot ratio:     " << (bench_config.hotspot_ratio * 100) << "%" << endl;
    cout << "  Hotspot size:      " << bench_config.hotspot_size << " keys" << endl;
    cout << "  Pin cores:         " << (bench_config.pin_cores ? "yes" : "no") << endl;
    cout << "==========================================" << endl;
    cout << endl;
}

void print_results(double duration_sec) {
    uint64_t total_committed = committed_txns.load();
    uint64_t total_aborted = aborted_txns.load();
    uint64_t total_txns = total_committed + total_aborted;
    uint64_t total_r = total_reads.load();
    uint64_t total_w = total_writes.load();
    
    double throughput = total_committed / duration_sec;
    double abort_rate = total_txns > 0 ? (total_aborted * 100.0) / total_txns : 0.0;
    
    cout << "==========================================" << endl;
    cout << "Results" << endl;
    cout << "==========================================" << endl;
    cout << fixed << setprecision(2);
    cout << "Duration:            " << duration_sec << " seconds" << endl;
    cout << "Committed:           " << total_committed << " transactions" << endl;
    cout << "Aborted:             " << total_aborted << " transactions" << endl;
    cout << "Total:               " << total_txns << " transactions" << endl;
    cout << "Abort rate:          " << abort_rate << "%" << endl;
    cout << "Throughput:          " << throughput << " txns/sec" << endl;
    cout << "Throughput/core:     " << (throughput / bench_config.num_threads) << " txns/sec/core" << endl;
    cout << "Total reads:         " << total_r << endl;
    cout << "Total writes:        " << total_w << endl;
    cout << endl;
    
    // Print performance counters if available
    if (bench_config.enable_profiling) {
        cout << "Performance Counters:" << endl;
        auto counters = event_counter::get_all_counters();
        for (const auto &p : counters) {
            cout << "  " << p.first << ": " << p.second << endl;
        }
    }
    
    // Print TSC-based performance probes
    cout << endl;
    cout << "Protocol Phase Timings (from performance probes):" << endl;
    cout << "  (Note: Use --enable-performance-profiling for detailed breakdown)" << endl;
}

int main(int argc, char **argv) {
    parse_args(argc, argv);
    print_config();
    
    abstract_db *db = new mbta_wrapper;
    db->init();
    
    // Setup configuration
    string config_path = get_current_absolute_path() + "../config/local-shards2-warehouses1.yml";
    auto config = new transport::Configuration(config_path);
    BenchmarkConfig::getInstance().setConfig(config);
    BenchmarkConfig::getInstance().setShardIndex(0);
    
    // Load initial data
    cout << "Loading initial data..." << endl;
    DataLoader loader(db, bench_config.num_keys);
    loader.load();
    cout << endl;
    
    // Create workers
    vector<SyntheticWorker*> workers;
    vector<thread> threads;
    vector<mt19937> rngs;
    
    random_device rd;
    for (int i = 0; i < bench_config.num_threads; i++) {
        rngs.emplace_back(rd() + i);
        workers.push_back(new SyntheticWorker(db, i, rngs[i]));
        workers[i]->initialize();
    }
    
    // Start benchmark
    auto start_time = chrono::high_resolution_clock::now();
    cout << "Starting benchmark..." << endl;
    cout << endl;
    
    // Launch threads
    for (int i = 0; i < bench_config.num_threads; i++) {
        threads.emplace_back([&workers, i]() {
            workers[i]->run();
        });
    }
    
    // Wait for all threads
    for (auto &t : threads) {
        t.join();
    }
    
    stop_flag = true;
    auto end_time = chrono::high_resolution_clock::now();
    double duration_sec = chrono::duration_cast<chrono::milliseconds>(end_time - start_time).count() / 1000.0;
    
    // Print results
    print_results(duration_sec);
    
    // Cleanup
    for (auto *w : workers) {
        delete w;
    }
    delete db;
    
    return 0;
}



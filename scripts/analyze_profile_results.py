#!/usr/bin/env python3
"""
Analyze batch validation profiling results
"""

import json
import sys
import os
from pathlib import Path
import argparse

def load_json_results(results_dir):
    """Load all JSON result files from the results directory"""
    results = {}
    results_path = Path(results_dir)
    
    for json_file in results_path.glob("*.json"):
        with open(json_file, 'r') as f:
            data = json.load(f)
            results[data['name']] = data
    
    return results

def print_comparison(results):
    """Print a comparison table of results"""
    
    baseline = results.get('baseline', {})
    batch_32 = results.get('batch_32', {})
    batch_64 = results.get('batch_64', {})
    
    # If no baseline, just show batch validation results
    has_baseline = bool(baseline)
    
    print("=" * 80)
    print("BATCH VALIDATION PROFILING RESULTS")
    print("=" * 80)
    print()
    
    # Throughput comparison
    print("--- Throughput Comparison ---")
    print(f"{'Metric':<30} {'Baseline':<20} {'Batch=32':<20} {'Batch=64':<20}")
    print("-" * 80)
    
    baseline_tput = baseline.get('throughput', {}).get('txns_per_second', 0)
    batch32_tput = batch_32.get('throughput', {}).get('txns_per_second', 0)
    batch64_tput = batch_64.get('throughput', {}).get('txns_per_second', 0)
    
    print(f"{'Throughput (txns/sec)':<30} {baseline_tput:<20.2f} {batch32_tput:<20.2f} {batch64_tput:<20.2f}")
    
    baseline_commits = baseline.get('throughput', {}).get('committed', 0)
    batch32_commits = batch_32.get('throughput', {}).get('committed', 0)
    batch64_commits = batch_64.get('throughput', {}).get('committed', 0)
    
    print(f"{'Committed Transactions':<30} {baseline_commits:<20} {batch32_commits:<20} {batch64_commits:<20}")
    
    baseline_abort = baseline.get('throughput', {}).get('abort_rate', 0)
    batch32_abort = batch_32.get('throughput', {}).get('abort_rate', 0)
    batch64_abort = batch_64.get('throughput', {}).get('abort_rate', 0)
    
    print(f"{'Abort Rate':<30} {baseline_abort:<20.2f} {batch32_abort:<20.2f} {batch64_abort:<20.2f}")
    
    baseline_latency = baseline.get('throughput', {}).get('avg_latency_ms', 0)
    batch32_latency = batch_32.get('throughput', {}).get('avg_latency_ms', 0)
    batch64_latency = batch_64.get('throughput', {}).get('avg_latency_ms', 0)
    
    print(f"{'Avg Latency (ms)':<30} {baseline_latency:<20.2f} {batch32_latency:<20.2f} {batch64_latency:<20.2f}")
    
    print()
    
    # Calculate speedup
    if baseline_tput > 0:
        speedup32 = (batch32_tput / baseline_tput) * 100 - 100
        speedup64 = (batch64_tput / baseline_tput) * 100 - 100
        print(f"Speedup vs Baseline: Batch=32: {speedup32:+.2f}%, Batch=64: {speedup64:+.2f}%")
        print()
    
    # Performance counter breakdown
    print("--- Performance Counter Breakdown (microseconds) ---")
    print(f"{'Phase':<30} {'Baseline':<20} {'Batch=32':<20} {'Batch=64':<20}")
    print("-" * 80)
    
    perf_fields = [
        ('Total Commit Time', 'total_commit_time_us'),
        ('Validation Time', 'validation_time_us'),
        ('Read Validation', 'read_validation_time_us'),
        ('Absent Validation', 'absent_validation_time_us'),
    ]
    
    for label, field in perf_fields:
        baseline_val = baseline.get('performance_counters', {}).get(field, 0)
        batch32_val = batch_32.get('performance_counters', {}).get(field, 0)
        batch64_val = batch_64.get('performance_counters', {}).get(field, 0)
        print(f"{label:<30} {baseline_val:<20.2f} {batch32_val:<20.2f} {batch64_val:<20.2f}")
    
    print()
    
    # Batch validation overhead
    if batch_32.get('batch_validation_enabled'):
        print("--- Batch Validation Overhead (Batch=32) ---")
        batch_data = batch_32.get('batch_validation', {})
        print(f"Batch Validations: {batch_data.get('batch_validations', 0)}")
        print(f"Validated Transactions: {batch_data.get('batch_validated_txns', 0)}")
        print(f"Aborted Transactions: {batch_data.get('batch_aborted_txns', 0)}")
        print(f"Avg Batch Size: {batch_data.get('avg_batch_size', 0):.2f}")
        print(f"Avg Batch Validation Time (us): {batch_data.get('avg_batch_validation_time_us', 0):.2f}")
        print(f"Avg Mutex Wait Time (us): {batch_data.get('avg_mutex_wait_us', 0):.2f}")
        print(f"Avg Batch Wait Time (us): {batch_data.get('avg_batch_wait_us', 0):.2f}")
        print(f"Avg Collection Time (us): {batch_data.get('avg_collection_time_us', 0):.2f}")
        print()
        
        # Calculate overhead percentage
        total_batch_overhead = (
            batch_data.get('avg_mutex_wait_us', 0) +
            batch_data.get('avg_batch_wait_us', 0) +
            batch_data.get('avg_collection_time_us', 0)
        )
        validation_time = batch_32.get('performance_counters', {}).get('validation_time_us', 0)
        
        if validation_time > 0:
            overhead_pct = (total_batch_overhead / validation_time) * 100
            print(f"Total Batch Overhead: {total_batch_overhead:.2f} us")
            print(f"Overhead as % of Validation Time: {overhead_pct:.2f}%")
            print()
    
    # Bottleneck analysis
    print("--- Bottleneck Analysis ---")
    baseline_perf = baseline.get('performance_counters', {})
    
    total_time = baseline_perf.get('total_commit_time_us', 0)
    if total_time > 0:
        validation_pct = (baseline_perf.get('validation_time_us', 0) / total_time) * 100
        read_val_pct = (baseline_perf.get('read_validation_time_us', 0) / total_time) * 100
        absent_val_pct = (baseline_perf.get('absent_validation_time_us', 0) / total_time) * 100
        
        print(f"Validation time: {validation_pct:.2f}% of total commit time")
        print(f"  - Read validation: {read_val_pct:.2f}%")
        print(f"  - Absent validation: {absent_val_pct:.2f}%")
        
        if validation_pct < 20:
            print()
            print("⚠️  WARNING: Validation is < 20% of total commit time!")
            print("   Batch validation may not help much - the bottleneck is elsewhere.")
    
    print()
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description='Analyze batch validation profiling results')
    parser.add_argument('results_dir', help='Directory containing profiling results')
    args = parser.parse_args()
    
    if not os.path.isdir(args.results_dir):
        print(f"Error: Results directory not found: {args.results_dir}")
        sys.exit(1)
    
    results = load_json_results(args.results_dir)
    
    if not results:
        print(f"Error: No JSON results found in {args.results_dir}")
        sys.exit(1)
    
    print_comparison(results)

if __name__ == '__main__':
    main()


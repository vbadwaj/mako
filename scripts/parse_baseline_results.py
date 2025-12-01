#!/usr/bin/env python3
"""
Parse baseline performance results and extract phase breakdowns
from Mako performance counters and probes.
"""

import json
import re
import sys
import os
from pathlib import Path
from collections import defaultdict

def parse_log_file(log_file):
    """Parse a single log file and extract metrics"""
    results = {
        'throughput': {},
        'commits': 0,
        'aborts': 0,
        'counters': {},
        'probes': {}
    }
    
    if not os.path.exists(log_file):
        print(f"Warning: Log file not found: {log_file}", file=sys.stderr)
        return results
    
    with open(log_file, 'r') as f:
        content = f.read()
    
    # Extract throughput (prefer agg_throughput as it's the aggregate)
    throughput_match = re.search(r'agg_throughput[:\s]+([\d.]+)', content, re.IGNORECASE)
    if not throughput_match:
        throughput_match = re.search(r'throughput[:\s]+([\d.]+)', content, re.IGNORECASE)
    if throughput_match:
        results['throughput']['txns_per_second'] = float(throughput_match.group(1))
    
    # Extract latency metrics
    latency_match = re.search(r'avg_latency[:\s]+([\d.]+)', content, re.IGNORECASE)
    if latency_match:
        results['latency'] = {'avg_ms': float(latency_match.group(1))}
    
    # Extract commit/abort counts
    # Look for n_commits (actual format in logs)
    commit_match = re.search(r'^n_commits[:\s]+(\d+)', content, re.MULTILINE | re.IGNORECASE)
    if not commit_match:
        commit_match = re.search(r'committed[:\s]+(\d+)', content, re.IGNORECASE)
    if commit_match:
        results['commits'] = int(commit_match.group(1))
    
    # For aborts, calculate from abort_rate * runtime
    # Extract abort rate and runtime
    abort_rate_match = re.search(r'agg_abort_rate[:\s]+([\d.]+)', content, re.IGNORECASE)
    runtime_match = re.search(r'runtime[:\s]+([\d.]+)', content, re.IGNORECASE)
    
    if abort_rate_match and runtime_match:
        abort_rate = float(abort_rate_match.group(1))
        runtime = float(runtime_match.group(1))
        results['aborts'] = int(abort_rate * runtime)
    else:
        # Fallback: try explicit abort count
        abort_match = re.search(r'n_aborts[:\s]+(\d+)', content, re.IGNORECASE)
        if abort_match:
            results['aborts'] = int(abort_match.group(1))
    
    # Extract performance counter stats
    # Look for counter patterns like "counter_name: count=1234"
    counter_pattern = r'([\w_]+)[:\s]+(?:count=)?(\d+)(?:[,\s]+(?:max|avg)=([\d.]+))?'
    counter_matches = re.finditer(counter_pattern, content)
    for match in counter_matches:
        name = match.group(1)
        count = int(match.group(2))
        value = float(match.group(3)) if match.group(3) else None
        results['counters'][name] = {
            'count': count,
            'value': value
        }
    
    # Extract probe timing from scopedperf output (if available)
    # Look for lines between "perf counters" and next section
    probe_section = False
    lines = content.split('\n')
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if 'perf counters' in line_stripped.lower() and 'if enabled' in line_stripped.lower():
            probe_section = True
            continue
        if probe_section:
            # Stop at next section header
            if line_stripped.startswith('---') and 'perf counters' not in line_stripped.lower():
                probe_section = False
                break
            # Parse probe line: should have probe name and numeric values
            if line_stripped and not line_stripped.startswith('---') and not line_stripped.startswith('2025'):
                parts = line_stripped.split()
                if len(parts) > 1:
                    probe_name = parts[0]
                    # Skip if it looks like a timestamp or log entry
                    if not probe_name.startswith('2025') and not '[' in probe_name:
                        try:
                            # Try to parse numeric values
                            nums = [float(x) for x in parts[1:] if re.match(r'^-?\d+\.?\d*$', x)]
                            if nums:
                                total = sum(nums)
                                if total > 0:
                                    results['probes'][probe_name] = total
                        except (ValueError, IndexError):
                            pass
    
    # Extract transaction type latency breakdown
    txn_latencies = {}
    for txn_type in ['NewOrder', 'Payment', 'Delivery', 'OrderStatus', 'StockLevel']:
        pattern = rf'{txn_type}_local_commit_latency[:\s]+([\d.]+)'
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            txn_latencies[txn_type] = float(match.group(1))
    
    if txn_latencies:
        results['txn_latencies'] = txn_latencies
    
    return results

def parse_directory(results_dir):
    """Parse all results in a directory"""
    results_dir = Path(results_dir)
    all_results = {}
    
    # Find all JSON and log files
    for json_file in results_dir.glob("baseline_*cores.json"):
        # Extract core count from filename
        match = re.search(r'baseline_(\d+)cores\.json', json_file.name)
        if match:
            cores = int(match.group(1))
            
            # Load JSON
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Parse corresponding log file
            log_file = json_file.with_suffix('.log')
            parsed_log = parse_log_file(str(log_file))
            
            # Merge results
            all_results[cores] = {
                **data,
                'metrics': parsed_log
            }
    
    return all_results

def calculate_phase_breakdown(results):
    """Calculate phase breakdown percentages from probe timings"""
    breakdown = {}
    
    # If we have probe timings, calculate percentages
    if 'probes' in results.get('metrics', {}):
        probes = results['metrics']['probes']
        if probes:
            total_time = sum(probes.values())
            if total_time > 0:
                for probe_name, timing in probes.items():
                    percentage = (timing / total_time) * 100
                    breakdown[probe_name] = {
                        'time': timing,
                        'percentage': percentage
                    }
    
    return breakdown

def print_summary(all_results):
    """Print a summary table of results"""
    print("=" * 80)
    print("Baseline Performance Summary")
    print("=" * 80)
    print()
    
    # Header
    print(f"{'Cores':<8} {'Throughput':<15} {'Committed':<12} {'Aborted':<12} {'Abort Rate':<12}")
    print("-" * 80)
    
    # Results for each core count
    for cores in sorted(all_results.keys()):
        result = all_results[cores]
        
        throughput = result.get('throughput', {}).get('txns_per_second', 0)
        commits = result.get('throughput', {}).get('committed', 0)
        aborts = result.get('throughput', {}).get('aborted', 0)
        total = commits + aborts
        abort_rate = (aborts / total * 100) if total > 0 else 0
        
        print(f"{cores:<8} {throughput:<15.2f} {commits:<12} {aborts:<12} {abort_rate:<12.2f}%")
    
    print()

def print_phase_breakdown(all_results):
    """Print phase breakdown for each core count"""
    print("=" * 80)
    print("Protocol Phase Breakdown")
    print("=" * 80)
    print()
    
    # First try to print probe-based breakdown
    has_probes = False
    for cores in sorted(all_results.keys()):
        result = all_results[cores]
        breakdown = calculate_phase_breakdown(result)
        
        if breakdown:
            has_probes = True
            print(f"Cores: {cores}")
            print(f"{'Phase':<40} {'Time (cycles)':<20} {'Percentage':<15}")
            print("-" * 80)
            
            for phase, data in sorted(breakdown.items(), key=lambda x: x[1]['percentage'], reverse=True):
                print(f"{phase:<40} {data['time']:<20.2f} {data['percentage']:<15.2f}%")
            
            print()
    
    # If no probe data, show latency breakdown by transaction type and available metrics
    if not has_probes:
        print("Note: Detailed protocol phase probes not available in logs.")
        print("Showing available performance metrics:")
        print()
        
        for cores in sorted(all_results.keys()):
            result = all_results[cores]
            metrics = result.get('metrics', {})
            txn_latencies = metrics.get('txn_latencies', {})
            latency = metrics.get('latency', {}).get('avg_ms', 0)
            throughput = result.get('throughput', {}).get('txns_per_second', 0)
            commits = result.get('throughput', {}).get('committed', 0)
            aborts = result.get('throughput', {}).get('aborted', 0)
            runtime = result.get('actual_duration', 0)
            
            print(f"Cores: {cores}")
            print(f"{'Metric':<35} {'Value':<20}")
            print("-" * 60)
            if throughput:
                print(f"{'Throughput':<35} {throughput:<20.2f} txns/sec")
            if latency:
                print(f"{'Average Latency':<35} {latency:<20.4f} ms")
            if commits:
                print(f"{'Total Commits':<35} {commits:<20,}")
            if aborts:
                print(f"{'Total Aborts':<35} {aborts:<20,}")
            if runtime:
                print(f"{'Runtime':<35} {runtime:<20.2f} sec")
            
            if txn_latencies:
                print()
                print(f"  Transaction Type Latencies:")
                for txn_type, lat in sorted(txn_latencies.items()):
                    print(f"    {txn_type:<30} {lat:<20.4f} ms")
            print()

def export_json_summary(all_results, output_file):
    """Export comprehensive summary to JSON"""
    summary = {
        'baseline_results': {}
    }
    
    for cores, result in all_results.items():
        breakdown = calculate_phase_breakdown(result)
        summary['baseline_results'][cores] = {
            'core_count': cores,
            'throughput': result.get('throughput', {}),
            'phase_breakdown': breakdown,
            'metrics': result.get('metrics', {})
        }
    
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary exported to: {output_file}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 parse_baseline_results.py <results_directory>")
        print()
        print("Example:")
        print("  python3 parse_baseline_results.py results/baseline_performance")
        sys.exit(1)
    
    results_dir = sys.argv[1]
    
    if not os.path.isdir(results_dir):
        print(f"Error: Directory not found: {results_dir}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Parsing results from: {results_dir}")
    print()
    
    # Parse all results
    all_results = parse_directory(results_dir)
    
    if not all_results:
        print("No results found. Expected files like:")
        print("  baseline_1cores.json, baseline_1cores.log")
        print("  baseline_2cores.json, baseline_2cores.log")
        print("  ...")
        sys.exit(1)
    
    # Print summaries
    print_summary(all_results)
    print_phase_breakdown(all_results)
    
    # Export JSON summary
    output_file = os.path.join(results_dir, 'summary.json')
    export_json_summary(all_results, output_file)

if __name__ == '__main__':
    main()



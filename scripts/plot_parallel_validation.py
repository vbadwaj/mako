#!/usr/bin/env python3
"""
Generate graphs for Parallel Batch Validation Micro-Benchmark results.

Usage:
    python3 plot_parallel_validation.py [csv_file] [output_dir]
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import sys
import os

# Style configuration
plt.style.use('seaborn-v0_8-whitegrid')
COLORS = {
    'sequential': '#E74C3C',   # Red
    'parallel': '#2ECC71',     # Green
    'speedup': '#3498DB',      # Blue
    'improvement': '#9B59B6',  # Purple
}

def load_data(csv_file):
    """Load benchmark results from CSV."""
    df = pd.read_csv(csv_file)
    return df

def plot_batch_size_impact(df, output_dir):
    """Plot the impact of batch size on performance."""
    # Filter for batch size test (read_set=50, threads=8)
    batch_df = df[(df['read_set_size'] == 50) & (df['num_threads'] == 8)].copy()
    batch_df = batch_df.sort_values('batch_size')
    
    if batch_df.empty:
        print("No batch size data found")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Impact of Batch Size on Parallel Validation Performance', fontsize=14, fontweight='bold')
    
    # 1. Throughput comparison
    ax1 = axes[0, 0]
    x = np.arange(len(batch_df))
    width = 0.35
    ax1.bar(x - width/2, batch_df['seq_throughput']/1e6, width, label='Sequential', color=COLORS['sequential'])
    ax1.bar(x + width/2, batch_df['par_throughput']/1e6, width, label='Parallel', color=COLORS['parallel'])
    ax1.set_xlabel('Batch Size')
    ax1.set_ylabel('Throughput (M txns/sec)')
    ax1.set_title('Throughput Comparison')
    ax1.set_xticks(x)
    ax1.set_xticklabels(batch_df['batch_size'])
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Latency comparison
    ax2 = axes[0, 1]
    ax2.bar(x - width/2, batch_df['seq_latency_us'], width, label='Sequential', color=COLORS['sequential'])
    ax2.bar(x + width/2, batch_df['par_latency_us'], width, label='Parallel', color=COLORS['parallel'])
    ax2.set_xlabel('Batch Size')
    ax2.set_ylabel('Latency (μs)')
    ax2.set_title('Latency Comparison')
    ax2.set_xticks(x)
    ax2.set_xticklabels(batch_df['batch_size'])
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Speedup
    ax3 = axes[1, 0]
    colors = [COLORS['parallel'] if s >= 1.0 else COLORS['sequential'] for s in batch_df['speedup']]
    bars = ax3.bar(x, batch_df['speedup'], color=colors)
    ax3.axhline(y=1.0, color='black', linestyle='--', linewidth=1, label='Breakeven')
    ax3.set_xlabel('Batch Size')
    ax3.set_ylabel('Speedup (x)')
    ax3.set_title('Parallel Speedup vs Sequential')
    ax3.set_xticks(x)
    ax3.set_xticklabels(batch_df['batch_size'])
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    # Add value labels
    for bar, val in zip(bars, batch_df['speedup']):
        ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, 
                f'{val:.2f}x', ha='center', va='bottom', fontsize=9)
    
    # 4. Throughput improvement %
    ax4 = axes[1, 1]
    improvement = batch_df['throughput_improvement']
    colors = [COLORS['parallel'] if i >= 0 else COLORS['sequential'] for i in improvement]
    bars = ax4.bar(x, improvement, color=colors)
    ax4.axhline(y=0, color='black', linestyle='--', linewidth=1)
    ax4.set_xlabel('Batch Size')
    ax4.set_ylabel('Throughput Improvement (%)')
    ax4.set_title('Throughput Improvement with Parallel Validation')
    ax4.set_xticks(x)
    ax4.set_xticklabels(batch_df['batch_size'])
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'batch_size_impact.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_dir}/batch_size_impact.png")

def plot_thread_count_impact(df, output_dir):
    """Plot the impact of thread count on performance."""
    # Filter for thread count test (batch=256, read_set=50)
    thread_df = df[(df['batch_size'] == 256) & (df['read_set_size'] == 50)].copy()
    thread_df = thread_df.sort_values('num_threads')
    
    if thread_df.empty:
        print("No thread count data found")
        return
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('Impact of Thread Count on Parallel Validation (batch_size=256)', fontsize=14, fontweight='bold')
    
    x = np.arange(len(thread_df))
    
    # 1. Throughput
    ax1 = axes[0]
    ax1.plot(thread_df['num_threads'], thread_df['seq_throughput']/1e6, 'o-', 
             label='Sequential', color=COLORS['sequential'], linewidth=2, markersize=8)
    ax1.plot(thread_df['num_threads'], thread_df['par_throughput']/1e6, 's-', 
             label='Parallel', color=COLORS['parallel'], linewidth=2, markersize=8)
    ax1.set_xlabel('Number of Threads')
    ax1.set_ylabel('Throughput (M txns/sec)')
    ax1.set_title('Throughput vs Thread Count')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(thread_df['num_threads'])
    
    # 2. Latency
    ax2 = axes[1]
    ax2.plot(thread_df['num_threads'], thread_df['seq_latency_us'], 'o-', 
             label='Sequential', color=COLORS['sequential'], linewidth=2, markersize=8)
    ax2.plot(thread_df['num_threads'], thread_df['par_latency_us'], 's-', 
             label='Parallel', color=COLORS['parallel'], linewidth=2, markersize=8)
    ax2.set_xlabel('Number of Threads')
    ax2.set_ylabel('Latency (μs)')
    ax2.set_title('Latency vs Thread Count')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(thread_df['num_threads'])
    
    # 3. Speedup
    ax3 = axes[2]
    ax3.plot(thread_df['num_threads'], thread_df['speedup'], 'o-', 
             color=COLORS['speedup'], linewidth=2, markersize=8)
    ax3.axhline(y=1.0, color='black', linestyle='--', linewidth=1, label='Breakeven')
    ax3.fill_between(thread_df['num_threads'], 1.0, thread_df['speedup'], 
                     where=(thread_df['speedup'] >= 1.0), alpha=0.3, color=COLORS['parallel'])
    ax3.fill_between(thread_df['num_threads'], thread_df['speedup'], 1.0, 
                     where=(thread_df['speedup'] < 1.0), alpha=0.3, color=COLORS['sequential'])
    ax3.set_xlabel('Number of Threads')
    ax3.set_ylabel('Speedup (x)')
    ax3.set_title('Speedup vs Thread Count')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_xticks(thread_df['num_threads'])
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'thread_count_impact.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_dir}/thread_count_impact.png")

def plot_read_set_impact(df, output_dir):
    """Plot the impact of read set size on performance."""
    # Filter for read set test (batch=64, threads=8)
    rs_df = df[(df['batch_size'] == 64) & (df['num_threads'] == 8)].copy()
    rs_df = rs_df.sort_values('read_set_size')
    
    if rs_df.empty:
        print("No read set data found")
        return
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('Impact of Read Set Size on Parallel Validation (batch_size=64, threads=8)', fontsize=14, fontweight='bold')
    
    # 1. Throughput
    ax1 = axes[0]
    ax1.plot(rs_df['read_set_size'], rs_df['seq_throughput']/1e6, 'o-', 
             label='Sequential', color=COLORS['sequential'], linewidth=2, markersize=8)
    ax1.plot(rs_df['read_set_size'], rs_df['par_throughput']/1e6, 's-', 
             label='Parallel', color=COLORS['parallel'], linewidth=2, markersize=8)
    ax1.set_xlabel('Read Set Size (items/txn)')
    ax1.set_ylabel('Throughput (M txns/sec)')
    ax1.set_title('Throughput vs Read Set Size')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. Latency
    ax2 = axes[1]
    ax2.plot(rs_df['read_set_size'], rs_df['seq_latency_us'], 'o-', 
             label='Sequential', color=COLORS['sequential'], linewidth=2, markersize=8)
    ax2.plot(rs_df['read_set_size'], rs_df['par_latency_us'], 's-', 
             label='Parallel', color=COLORS['parallel'], linewidth=2, markersize=8)
    ax2.set_xlabel('Read Set Size (items/txn)')
    ax2.set_ylabel('Latency (μs)')
    ax2.set_title('Latency vs Read Set Size')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. Speedup
    ax3 = axes[2]
    ax3.bar(range(len(rs_df)), rs_df['speedup'], 
            color=[COLORS['parallel'] if s >= 1.0 else COLORS['sequential'] for s in rs_df['speedup']])
    ax3.axhline(y=1.0, color='black', linestyle='--', linewidth=1, label='Breakeven')
    ax3.set_xlabel('Read Set Size (items/txn)')
    ax3.set_ylabel('Speedup (x)')
    ax3.set_title('Speedup vs Read Set Size')
    ax3.set_xticks(range(len(rs_df)))
    ax3.set_xticklabels(rs_df['read_set_size'])
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    # Add value labels
    for i, (_, row) in enumerate(rs_df.iterrows()):
        ax3.text(i, row['speedup'] + 0.05, f"{row['speedup']:.2f}x", ha='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'read_set_impact.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_dir}/read_set_impact.png")

def plot_summary(df, output_dir):
    """Create a summary heatmap of speedup across configurations."""
    # Create pivot table for batch size vs threads
    batch_thread_df = df[df['read_set_size'] == 50].copy()
    
    if batch_thread_df.empty:
        print("No summary data found")
        return
    
    # Get unique batch sizes and thread counts
    batch_sizes = sorted(batch_thread_df['batch_size'].unique())
    thread_counts = sorted(batch_thread_df['num_threads'].unique())
    
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.suptitle('Summary: When Does Parallel Validation Help?', fontsize=14, fontweight='bold')
    
    # Create a summary bar chart showing speedup ranges
    categories = ['batch<32', 'batch=32-64', 'batch=128-256', 'batch>256']
    speedups = []
    
    for cat in categories:
        if cat == 'batch<32':
            mask = batch_thread_df['batch_size'] < 32
        elif cat == 'batch=32-64':
            mask = (batch_thread_df['batch_size'] >= 32) & (batch_thread_df['batch_size'] <= 64)
        elif cat == 'batch=128-256':
            mask = (batch_thread_df['batch_size'] >= 128) & (batch_thread_df['batch_size'] <= 256)
        else:
            mask = batch_thread_df['batch_size'] > 256
        
        if mask.any():
            speedups.append(batch_thread_df[mask]['speedup'].mean())
        else:
            speedups.append(1.0)
    
    colors = [COLORS['parallel'] if s >= 1.0 else COLORS['sequential'] for s in speedups]
    bars = ax.bar(categories, speedups, color=colors, edgecolor='black', linewidth=1.2)
    ax.axhline(y=1.0, color='black', linestyle='--', linewidth=2, label='Breakeven (1.0x)')
    
    ax.set_ylabel('Average Speedup (x)', fontsize=12)
    ax.set_xlabel('Batch Size Category', fontsize=12)
    ax.set_title('Average Speedup by Batch Size Category', fontsize=12)
    ax.legend(loc='upper left')
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bar, val in zip(bars, speedups):
        label = f'{val:.2f}x'
        if val >= 1.0:
            label += '\n✓ Benefit'
        else:
            label += '\n✗ Overhead'
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02, 
                label, ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    ax.set_ylim(0, max(speedups) * 1.3)
    
    plt.tight_layout()
    plt.savefig(os.path.join(output_dir, 'summary.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_dir}/summary.png")

def main():
    # Parse arguments
    csv_file = sys.argv[1] if len(sys.argv) > 1 else '/home/ubuntu/mako/results/perf_profiles/parallel_validation_results.csv'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else '/home/ubuntu/mako/results/perf_profiles'
    
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Loading data from: {csv_file}")
    df = load_data(csv_file)
    print(f"Loaded {len(df)} data points")
    
    print("\nGenerating graphs...")
    plot_batch_size_impact(df, output_dir)
    plot_thread_count_impact(df, output_dir)
    plot_read_set_impact(df, output_dir)
    plot_summary(df, output_dir)
    
    print("\nAll graphs generated successfully!")
    print(f"\nOutput files in: {output_dir}/")
    print("  - batch_size_impact.png")
    print("  - thread_count_impact.png")
    print("  - read_set_impact.png")
    print("  - summary.png")

if __name__ == '__main__':
    main()


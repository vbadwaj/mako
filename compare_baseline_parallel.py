#!/usr/bin/env python3
"""
Compare Baseline vs Parallel Batch Validation Performance Results
"""

import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Set style
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 11

def load_results(results_dir, prefix):
    """Load results from JSON files"""
    results_list = []
    results_path = Path(results_dir)
    
    for json_file in sorted(results_path.glob(f"{prefix}_*cores.json")):
        try:
            # Read file content and fix common JSON issues
            with open(json_file, 'r') as f:
                content = f.read()
            
            # Try to fix empty values in JSON (replace ",," with ",0," or ",null,")
            # This handles cases where values are missing
            import re
            content = re.sub(r':\s*,', ': null,', content)
            content = re.sub(r':\s*(\n\s*[}\]])', r': null\1', content)
            
            data = json.loads(content)
            
            core_count = data.get('core_count', 0)
            throughput = data.get('throughput', {}).get('txns_per_second', 0) or 0
            committed = data.get('throughput', {}).get('committed', 0) or 0
            aborted = data.get('throughput', {}).get('aborted', 0) or 0
            abort_rate = (aborted / (committed + aborted) * 100) if (committed + aborted) > 0 else 0
            
            results_list.append({
                'cores': core_count,
                'throughput': float(throughput),
                'committed': float(committed),
                'aborted': float(aborted),
                'abort_rate': abort_rate,
                'per_core_throughput': float(throughput) / core_count if core_count > 0 else 0
            })
        except Exception as e:
            print(f"Warning: Could not load {json_file}: {e}")
            import traceback
            traceback.print_exc()
    
    if not results_list:
        return pd.DataFrame()
    
    return pd.DataFrame(results_list).sort_values('cores')

def main():
    baseline_dir = 'results/baseline_performance'
    parallel_dir = 'results/parallel_batch_validation'
    output_dir = Path('results/comparison')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Loading baseline results...")
    baseline_df = load_results(baseline_dir, 'baseline')
    
    print("Loading parallel batch validation results...")
    parallel_df = load_results(parallel_dir, 'parallel')
    
    if baseline_df.empty or parallel_df.empty:
        print("Error: Could not load results. Make sure both baseline and parallel tests have been run.")
        return
    
    print(f"\nBaseline results: {len(baseline_df)} configurations")
    print(f"Parallel results: {len(parallel_df)} configurations")
    
    # Merge on core count
    comparison = baseline_df.merge(
        parallel_df,
        on='cores',
        suffixes=('_baseline', '_parallel'),
        how='inner'
    )
    
    if comparison.empty:
        print("Error: No matching core counts found between baseline and parallel results.")
        return
    
    # Calculate improvements
    comparison['throughput_improvement'] = (
        (comparison['throughput_parallel'] - comparison['throughput_baseline']) / 
        comparison['throughput_baseline'] * 100
    )
    comparison['throughput_speedup'] = (
        comparison['throughput_parallel'] / comparison['throughput_baseline']
    )
    comparison['per_core_improvement'] = (
        (comparison['per_core_throughput_parallel'] - comparison['per_core_throughput_baseline']) /
        comparison['per_core_throughput_baseline'] * 100
    )
    
    # Print summary
    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON: Baseline vs Parallel Batch Validation")
    print("="*80)
    print(f"\n{'Cores':<6} {'Baseline':<12} {'Parallel':<12} {'Speedup':<8} {'Improvement':<12}")
    print("-" * 80)
    for _, row in comparison.iterrows():
        print(f"{int(row['cores']):<6} "
              f"{row['throughput_baseline']:>10,.0f}  "
              f"{row['throughput_parallel']:>10,.0f}  "
              f"{row['throughput_speedup']:>6.2f}x  "
              f"{row['throughput_improvement']:>10.1f}%")
    
    # Save comparison to JSON
    comparison_json = {
        'comparison': comparison.to_dict('records'),
        'summary': {
            'max_speedup': float(comparison['throughput_speedup'].max()),
            'max_speedup_cores': int(comparison.loc[comparison['throughput_speedup'].idxmax(), 'cores']),
            'avg_speedup': float(comparison['throughput_speedup'].mean()),
            'max_improvement_pct': float(comparison['throughput_improvement'].max()),
            'avg_improvement_pct': float(comparison['throughput_improvement'].mean())
        }
    }
    
    with open(output_dir / 'comparison.json', 'w') as f:
        json.dump(comparison_json, f, indent=2)
    
    print(f"\n✓ Comparison saved to: {output_dir / 'comparison.json'}")
    
    # Create visualizations
    print("\nGenerating comparison visualizations...")
    
    # 1. Throughput Comparison
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # Plot 1: Absolute throughput
    ax1.plot(comparison['cores'], comparison['throughput_baseline'], 
             marker='o', linewidth=2.5, markersize=10, 
             label='Baseline (Sequential)', color='#2E86AB')
    ax1.plot(comparison['cores'], comparison['throughput_parallel'], 
             marker='s', linewidth=2.5, markersize=10, 
             label='Parallel Batch Validation', color='#A23B72')
    
    ax1.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Throughput (txns/sec)', fontsize=12, fontweight='bold')
    ax1.set_title('Throughput Comparison: Baseline vs Parallel', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(comparison['cores'])
    
    # Add value labels
    for _, row in comparison.iterrows():
        ax1.annotate(f'{row["throughput_baseline"]:.0f}', 
                    (row['cores'], row['throughput_baseline']),
                    textcoords="offset points", xytext=(0,10), ha='center', fontsize=8)
        ax1.annotate(f'{row["throughput_parallel"]:.0f}', 
                    (row['cores'], row['throughput_parallel']),
                    textcoords="offset points", xytext=(0,-15), ha='center', fontsize=8)
    
    # Plot 2: Speedup
    ax2.bar(comparison['cores'], comparison['throughput_speedup'], 
            color='#06A77D', alpha=0.7, edgecolor='black', linewidth=1.5)
    ax2.axhline(y=1.0, linestyle='--', color='red', alpha=0.6, label='No improvement (1.0x)')
    ax2.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Speedup (x)', fontsize=12, fontweight='bold')
    ax2.set_title('Throughput Speedup: Parallel vs Baseline', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_xticks(comparison['cores'])
    
    # Add value labels
    for _, row in comparison.iterrows():
        ax2.annotate(f'{row["throughput_speedup"]:.2f}x', 
                    (row['cores'], row['throughput_speedup']),
                    textcoords="offset points", xytext=(0,5), ha='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'throughput_comparison.png', dpi=150, bbox_inches='tight')
    print(f"✓ Saved: {output_dir / 'throughput_comparison.png'}")
    
    # 2. Per-Core Efficiency Comparison
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # Plot 1: Per-core throughput
    ax1.plot(comparison['cores'], comparison['per_core_throughput_baseline'], 
             marker='o', linewidth=2.5, markersize=10, 
             label='Baseline', color='#2E86AB')
    ax1.plot(comparison['cores'], comparison['per_core_throughput_parallel'], 
             marker='s', linewidth=2.5, markersize=10, 
             label='Parallel', color='#A23B72')
    
    ax1.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Per-Core Throughput (txns/sec/core)', fontsize=12, fontweight='bold')
    ax1.set_title('Per-Core Efficiency Comparison', fontsize=14, fontweight='bold')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(comparison['cores'])
    
    # Plot 2: Improvement percentage
    colors = ['green' if x > 0 else 'red' for x in comparison['throughput_improvement']]
    ax2.bar(comparison['cores'], comparison['throughput_improvement'], 
            color=colors, alpha=0.7, edgecolor='black', linewidth=1.5)
    ax2.axhline(y=0, linestyle='-', color='black', linewidth=1)
    ax2.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Improvement (%)', fontsize=12, fontweight='bold')
    ax2.set_title('Throughput Improvement Percentage', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_xticks(comparison['cores'])
    
    # Add value labels
    for _, row in comparison.iterrows():
        ax2.annotate(f'{row["throughput_improvement"]:+.1f}%', 
                    (row['cores'], row['throughput_improvement']),
                    textcoords="offset points", xytext=(0,5 if row['throughput_improvement'] > 0 else -15), 
                    ha='center', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'efficiency_comparison.png', dpi=150, bbox_inches='tight')
    print(f"✓ Saved: {output_dir / 'efficiency_comparison.png'}")
    
    # 3. Abort Rate Comparison
    fig, ax = plt.subplots(1, 1, figsize=(10, 6))
    
    x = np.arange(len(comparison))
    width = 0.35
    
    ax.bar(x - width/2, comparison['abort_rate_baseline'], width, 
           label='Baseline', color='#2E86AB', alpha=0.7, edgecolor='black')
    ax.bar(x + width/2, comparison['abort_rate_parallel'], width, 
           label='Parallel', color='#A23B72', alpha=0.7, edgecolor='black')
    
    ax.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
    ax.set_ylabel('Abort Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('Abort Rate Comparison', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels([int(c) for c in comparison['cores']])
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'abort_rate_comparison.png', dpi=150, bbox_inches='tight')
    print(f"✓ Saved: {output_dir / 'abort_rate_comparison.png'}")
    
    # 4. Comprehensive Dashboard
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # 1. Throughput (top, spans 2 columns)
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(comparison['cores'], comparison['throughput_baseline'], 
             marker='o', linewidth=3, markersize=12, label='Baseline', color='#2E86AB')
    ax1.plot(comparison['cores'], comparison['throughput_parallel'], 
             marker='s', linewidth=3, markersize=12, label='Parallel', color='#A23B72')
    ax1.set_xlabel('Number of Cores', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Throughput (txns/sec)', fontsize=11, fontweight='bold')
    ax1.set_title('Throughput Comparison', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(comparison['cores'])
    
    # 2. Speedup (top right)
    ax2 = fig.add_subplot(gs[0, 2])
    ax2.bar(comparison['cores'], comparison['throughput_speedup'], 
            color='#06A77D', alpha=0.7, edgecolor='black')
    ax2.axhline(y=1.0, linestyle='--', color='red', alpha=0.6)
    ax2.set_xlabel('Cores', fontsize=10, fontweight='bold')
    ax2.set_ylabel('Speedup (x)', fontsize=10, fontweight='bold')
    ax2.set_title('Speedup', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_xticks(comparison['cores'])
    
    # 3. Per-core efficiency (middle left)
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.plot(comparison['cores'], comparison['per_core_throughput_baseline'], 
             marker='o', linewidth=2.5, markersize=10, label='Baseline', color='#2E86AB')
    ax3.plot(comparison['cores'], comparison['per_core_throughput_parallel'], 
             marker='s', linewidth=2.5, markersize=10, label='Parallel', color='#A23B72')
    ax3.set_xlabel('Cores', fontsize=10, fontweight='bold')
    ax3.set_ylabel('Per-Core Throughput', fontsize=10, fontweight='bold')
    ax3.set_title('Per-Core Efficiency', fontsize=12, fontweight='bold')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.set_xticks(comparison['cores'])
    
    # 4. Improvement % (middle center)
    ax4 = fig.add_subplot(gs[1, 1])
    colors = ['green' if x > 0 else 'red' for x in comparison['throughput_improvement']]
    ax4.bar(comparison['cores'], comparison['throughput_improvement'], 
            color=colors, alpha=0.7, edgecolor='black')
    ax4.axhline(y=0, linestyle='-', color='black', linewidth=1)
    ax4.set_xlabel('Cores', fontsize=10, fontweight='bold')
    ax4.set_ylabel('Improvement (%)', fontsize=10, fontweight='bold')
    ax4.set_title('Improvement %', fontsize=12, fontweight='bold')
    ax4.grid(True, alpha=0.3, axis='y')
    ax4.set_xticks(comparison['cores'])
    
    # 5. Abort rate (middle right)
    ax5 = fig.add_subplot(gs[1, 2])
    x = np.arange(len(comparison))
    width = 0.35
    ax5.bar(x - width/2, comparison['abort_rate_baseline'], width, 
            label='Baseline', color='#2E86AB', alpha=0.7)
    ax5.bar(x + width/2, comparison['abort_rate_parallel'], width, 
            label='Parallel', color='#A23B72', alpha=0.7)
    ax5.set_xlabel('Cores', fontsize=10, fontweight='bold')
    ax5.set_ylabel('Abort Rate (%)', fontsize=10, fontweight='bold')
    ax5.set_title('Abort Rate', fontsize=12, fontweight='bold')
    ax5.set_xticks(x)
    ax5.set_xticklabels([int(c) for c in comparison['cores']])
    ax5.legend(fontsize=9)
    ax5.grid(True, alpha=0.3, axis='y')
    
    # 6. Speedup by core count (bottom, spans all)
    ax6 = fig.add_subplot(gs[2, :])
    bars = ax6.bar(comparison['cores'], comparison['throughput_speedup'], 
                   color='#06A77D', alpha=0.7, edgecolor='black', linewidth=1.5)
    ax6.axhline(y=1.0, linestyle='--', color='red', alpha=0.6, linewidth=2, label='Baseline (1.0x)')
    ax6.set_xlabel('Number of Cores', fontsize=11, fontweight='bold')
    ax6.set_ylabel('Speedup (x)', fontsize=11, fontweight='bold')
    ax6.set_title('Speedup by Core Count', fontsize=13, fontweight='bold')
    ax6.legend(fontsize=10)
    ax6.grid(True, alpha=0.3, axis='y')
    ax6.set_xticks(comparison['cores'])
    
    # Add value labels
    for bar, speedup in zip(bars, comparison['throughput_speedup']):
        height = bar.get_height()
        ax6.annotate(f'{speedup:.2f}x',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.suptitle('Baseline vs Parallel Batch Validation - Performance Comparison', 
                 fontsize=16, fontweight='bold', y=0.995)
    plt.savefig(output_dir / 'comparison_dashboard.png', dpi=150, bbox_inches='tight')
    print(f"✓ Saved: {output_dir / 'comparison_dashboard.png'}")
    
    # Print key insights
    print("\n" + "="*80)
    print("KEY INSIGHTS")
    print("="*80)
    max_speedup_row = comparison.loc[comparison['throughput_speedup'].idxmax()]
    print(f"✅ Maximum Speedup: {max_speedup_row['throughput_speedup']:.2f}x at {int(max_speedup_row['cores'])} cores")
    print(f"✅ Average Speedup: {comparison['throughput_speedup'].mean():.2f}x")
    print(f"✅ Maximum Improvement: {comparison['throughput_improvement'].max():.1f}%")
    print(f"✅ Average Improvement: {comparison['throughput_improvement'].mean():.1f}%")
    print("="*80)
    print(f"\n✅ All comparison results saved to: {output_dir}/")

if __name__ == '__main__':
    main()


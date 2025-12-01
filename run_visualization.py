#!/usr/bin/env python3
# Mako Baseline Performance Analysis

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

# Increase figure size for better readability
plt.rcParams['figure.figsize'] = (14, 8)
plt.rcParams['font.size'] = 11

print("Libraries loaded successfully!")

# Load the summary JSON file
results_dir = Path('results/baseline_performance')
summary_file = results_dir / 'summary.json'

with open(summary_file, 'r') as f:
    data = json.load(f)

# Extract baseline results
baseline = data['baseline_results']

# Create a list of dictionaries for DataFrame
results_list = []
for core_count, result in baseline.items():
    core_count = int(core_count)
    throughput = result['throughput']['txns_per_second']
    committed = result['throughput']['committed']
    aborted = result['throughput']['aborted']
    abort_rate = (aborted / (committed + aborted) * 100) if (committed + aborted) > 0 else 0
    avg_latency = result['metrics']['latency']['avg_ms']
    
    # Transaction latencies
    txn_latencies = result['metrics']['txn_latencies']
    
    results_list.append({
        'cores': core_count,
        'throughput': throughput,
        'committed': committed,
        'aborted': aborted,
        'abort_rate': abort_rate,
        'avg_latency_ms': avg_latency,
        'per_core_throughput': throughput / core_count,
        **{f'latency_{k}': v for k, v in txn_latencies.items()}
    })

# Create DataFrame
df = pd.DataFrame(results_list).sort_values('cores')

print(f"Loaded {len(df)} benchmark runs")
print(f"\nData summary:")
print(df[['cores', 'throughput', 'abort_rate', 'avg_latency_ms']].to_string(index=False))

## 1. Throughput Scaling
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Plot 1: Absolute throughput
ax1.plot(df['cores'], df['throughput'], marker='o', linewidth=2.5, markersize=10, 
         label='Total Throughput', color='#2E86AB')
ax1.axhline(y=df.iloc[0]['throughput'], linestyle='--', color='gray', alpha=0.5, 
            label=f"1-core baseline ({df.iloc[0]['throughput']:.0f} txns/s)")

# Add ideal linear scaling reference
ideal_scaling = df.iloc[0]['throughput'] * df['cores']
ax1.plot(df['cores'], ideal_scaling, linestyle=':', color='red', alpha=0.6, 
         label='Ideal Linear Scaling', linewidth=2)

ax1.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
ax1.set_ylabel('Throughput (txns/sec)', fontsize=12, fontweight='bold')
ax1.set_title('Total Throughput Scaling', fontsize=14, fontweight='bold')
ax1.legend(loc='upper left')
ax1.grid(True, alpha=0.3)
ax1.set_xticks(df['cores'])

# Add value labels
for _, row in df.iterrows():
    ax1.annotate(f'{row["throughput"]:.0f}', 
                (row['cores'], row['throughput']),
                textcoords="offset points", xytext=(0,10), ha='center', fontsize=9)

# Plot 2: Per-core throughput (efficiency)
ax2.plot(df['cores'], df['per_core_throughput'], marker='s', linewidth=2.5, 
         markersize=10, label='Per-Core Throughput', color='#A23B72')
ax2.axhline(y=df.iloc[0]['per_core_throughput'], linestyle='--', color='gray', 
            alpha=0.5, label=f"1-core baseline ({df.iloc[0]['per_core_throughput']:.0f} txns/s/core)")

ax2.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
ax2.set_ylabel('Throughput per Core (txns/sec/core)', fontsize=12, fontweight='bold')
ax2.set_title('Per-Core Throughput (Scaling Efficiency)', fontsize=14, fontweight='bold')
ax2.legend(loc='best')
ax2.grid(True, alpha=0.3)
ax2.set_xticks(df['cores'])

# Add value labels
for _, row in df.iterrows():
    ax2.annotate(f'{row["per_core_throughput"]:.0f}', 
                (row['cores'], row['per_core_throughput']),
                textcoords="offset points", xytext=(0,10), ha='center', fontsize=9)

plt.tight_layout()
plt.savefig('results/baseline_performance/throughput_scaling.png', dpi=150, bbox_inches='tight')
print("\nSaved: results/baseline_performance/throughput_scaling.png")

# Calculate efficiency metrics
print("\n" + "="*60)
print("Scaling Efficiency Analysis")
print("="*60)
for _, row in df.iterrows():
    efficiency = (row['per_core_throughput'] / df.iloc[0]['per_core_throughput']) * 100
    speedup = row['throughput'] / df.iloc[0]['throughput']
    ideal_speedup = row['cores']
    speedup_efficiency = (speedup / ideal_speedup) * 100
    print(f"{int(row['cores']):2d} cores: {speedup:5.2f}x speedup ({speedup_efficiency:5.1f}% of ideal), "
          f"Per-core efficiency: {efficiency:5.1f}%")

## 2. Latency Analysis
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Plot 1: Average latency
ax1.plot(df['cores'], df['avg_latency_ms'], marker='o', linewidth=2.5, 
         markersize=10, label='Average Latency', color='#F18F01')
ax1.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
ax1.set_ylabel('Average Latency (ms)', fontsize=12, fontweight='bold')
ax1.set_title('Average Transaction Latency', fontsize=14, fontweight='bold')
ax1.legend()
ax1.grid(True, alpha=0.3)
ax1.set_xticks(df['cores'])

# Add value labels
for _, row in df.iterrows():
    ax1.annotate(f'{row["avg_latency_ms"]:.3f}', 
                (row['cores'], row['avg_latency_ms']),
                textcoords="offset points", xytext=(0,10), ha='center', fontsize=9)

# Plot 2: Transaction type latencies
txn_types = ['NewOrder', 'Payment', 'Delivery', 'OrderStatus', 'StockLevel']
colors = plt.cm.Set3(np.linspace(0, 1, len(txn_types)))

x = np.arange(len(df))
width = 0.15

for i, txn_type in enumerate(txn_types):
    col_name = f'latency_{txn_type}'
    if col_name in df.columns:
        ax2.bar(x + i*width, df[col_name], width, label=txn_type, color=colors[i])

ax2.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
ax2.set_ylabel('Latency (ms)', fontsize=12, fontweight='bold')
ax2.set_title('Transaction Type Latencies by Core Count', fontsize=14, fontweight='bold')
ax2.set_xticks(x + width * 2)
ax2.set_xticklabels(df['cores'])
ax2.legend(loc='upper left', fontsize=9)
ax2.grid(True, alpha=0.3, axis='y')

plt.tight_layout()
plt.savefig('results/baseline_performance/latency_analysis.png', dpi=150, bbox_inches='tight')
print("\nSaved: results/baseline_performance/latency_analysis.png")

# Print latency table
print("\n" + "="*80)
print("Transaction Type Latencies (ms)")
print("="*80)
latency_cols = ['cores'] + [f'latency_{t}' for t in txn_types if f'latency_{t}' in df.columns]
latency_df = df[latency_cols].copy()
latency_df.columns = ['Cores'] + [col.replace('latency_', '') for col in latency_df.columns[1:]]
print(latency_df.to_string(index=False))

## 3. Abort Rate Analysis
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

# Plot 1: Abort rate percentage
ax1.plot(df['cores'], df['abort_rate'], marker='o', linewidth=2.5, 
         markersize=10, label='Abort Rate', color='#C73E1D')
ax1.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
ax1.set_ylabel('Abort Rate (%)', fontsize=12, fontweight='bold')
ax1.set_title('Transaction Abort Rate', fontsize=14, fontweight='bold')
ax1.legend()
ax1.grid(True, alpha=0.3)
ax1.set_xticks(df['cores'])

# Add value labels
for _, row in df.iterrows():
    ax1.annotate(f'{row["abort_rate"]:.2f}%', 
                (row['cores'], row['abort_rate']),
                textcoords="offset points", xytext=(0,10), ha='center', fontsize=9)

# Plot 2: Absolute abort counts
ax2.bar(df['cores'], df['aborted'], color='#E63946', alpha=0.7, edgecolor='black', linewidth=1.5)
ax2.set_xlabel('Number of Cores', fontsize=12, fontweight='bold')
ax2.set_ylabel('Number of Aborted Transactions', fontsize=12, fontweight='bold')
ax2.set_title('Absolute Abort Counts', fontsize=14, fontweight='bold')
ax2.set_xticks(df['cores'])
ax2.grid(True, alpha=0.3, axis='y')

# Add value labels
for _, row in df.iterrows():
    ax2.annotate(f'{int(row["aborted"])}', 
                (row['cores'], row['aborted']),
                textcoords="offset points", xytext=(0,5), ha='center', fontsize=9)

plt.tight_layout()
plt.savefig('results/baseline_performance/abort_analysis.png', dpi=150, bbox_inches='tight')
print("\nSaved: results/baseline_performance/abort_analysis.png")

# Print abort statistics
print("\n" + "="*60)
print("Abort Statistics")
print("="*60)
abort_df = df[['cores', 'committed', 'aborted', 'abort_rate']].copy()
abort_df.columns = ['Cores', 'Committed', 'Aborted', 'Abort Rate (%)']
abort_df['Total Txns'] = abort_df['Committed'] + abort_df['Aborted']
print(abort_df.to_string(index=False))

## 4. Comprehensive Performance Dashboard
# Create a comprehensive dashboard
fig = plt.figure(figsize=(18, 12))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

# 1. Throughput (top left, spans 2 columns)
ax1 = fig.add_subplot(gs[0, :2])
ax1.plot(df['cores'], df['throughput'], marker='o', linewidth=3, markersize=12, 
         label='Total Throughput', color='#2E86AB')
ideal = df.iloc[0]['throughput'] * df['cores']
ax1.plot(df['cores'], ideal, linestyle=':', color='red', alpha=0.6, 
         label='Ideal Linear Scaling', linewidth=2)
ax1.fill_between(df['cores'], df['throughput'], ideal, alpha=0.2, color='red')
ax1.set_xlabel('Number of Cores', fontsize=11, fontweight='bold')
ax1.set_ylabel('Throughput (txns/sec)', fontsize=11, fontweight='bold')
ax1.set_title('Total Throughput Scaling', fontsize=13, fontweight='bold')
ax1.legend(fontsize=10)
ax1.grid(True, alpha=0.3)
ax1.set_xticks(df['cores'])

# 2. Per-core efficiency (top right)
ax2 = fig.add_subplot(gs[0, 2])
ax2.plot(df['cores'], df['per_core_throughput'], marker='s', linewidth=2.5, 
         markersize=10, color='#A23B72')
ax2.axhline(y=df.iloc[0]['per_core_throughput'], linestyle='--', color='gray', alpha=0.5)
ax2.set_xlabel('Cores', fontsize=10, fontweight='bold')
ax2.set_ylabel('Throughput/Core', fontsize=10, fontweight='bold')
ax2.set_title('Per-Core Efficiency', fontsize=12, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.set_xticks(df['cores'])

# 3. Latency (middle left)
ax3 = fig.add_subplot(gs[1, 0])
ax3.plot(df['cores'], df['avg_latency_ms'], marker='o', linewidth=2.5, 
         markersize=10, color='#F18F01')
ax3.set_xlabel('Cores', fontsize=10, fontweight='bold')
ax3.set_ylabel('Avg Latency (ms)', fontsize=10, fontweight='bold')
ax3.set_title('Average Latency', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3)
ax3.set_xticks(df['cores'])

# 4. Abort rate (middle center)
ax4 = fig.add_subplot(gs[1, 1])
ax4.plot(df['cores'], df['abort_rate'], marker='o', linewidth=2.5, 
         markersize=10, color='#C73E1D')
ax4.set_xlabel('Cores', fontsize=10, fontweight='bold')
ax4.set_ylabel('Abort Rate (%)', fontsize=10, fontweight='bold')
ax4.set_title('Abort Rate', fontsize=12, fontweight='bold')
ax4.grid(True, alpha=0.3)
ax4.set_xticks(df['cores'])

# 5. Speedup (middle right)
ax5 = fig.add_subplot(gs[1, 2])
speedup = df['throughput'] / df.iloc[0]['throughput']
ideal_speedup = df['cores']
ax5.plot(df['cores'], speedup, marker='o', linewidth=2.5, markersize=10, 
         label='Actual', color='#06A77D')
ax5.plot(df['cores'], ideal_speedup, linestyle='--', linewidth=2, 
         label='Ideal', color='red', alpha=0.6)
ax5.set_xlabel('Cores', fontsize=10, fontweight='bold')
ax5.set_ylabel('Speedup (x)', fontsize=10, fontweight='bold')
ax5.set_title('Speedup vs Ideal', fontsize=12, fontweight='bold')
ax5.legend(fontsize=9)
ax5.grid(True, alpha=0.3)
ax5.set_xticks(df['cores'])

# 6. Transaction latencies heatmap (bottom, spans all columns)
ax6 = fig.add_subplot(gs[2, :])
txn_data = []
for _, row in df.iterrows():
    txn_row = [row['cores']]
    for txn_type in txn_types:
        col_name = f'latency_{txn_type}'
        if col_name in df.columns:
            txn_row.append(row[col_name])
        else:
            txn_row.append(0)
    txn_data.append(txn_row)

txn_df = pd.DataFrame(txn_data, columns=['Cores'] + txn_types)
txn_df.set_index('Cores', inplace=True)

sns.heatmap(txn_df.T, annot=True, fmt='.3f', cmap='YlOrRd', 
            cbar_kws={'label': 'Latency (ms)'}, ax=ax6, linewidths=0.5)
ax6.set_xlabel('Number of Cores', fontsize=11, fontweight='bold')
ax6.set_ylabel('Transaction Type', fontsize=11, fontweight='bold')
ax6.set_title('Transaction Type Latencies Heatmap', fontsize=13, fontweight='bold')

plt.suptitle('Mako Baseline Performance Dashboard - TPC-C Workload', 
             fontsize=16, fontweight='bold', y=0.995)
plt.savefig('results/baseline_performance/dashboard.png', dpi=150, bbox_inches='tight')
print("\nSaved: results/baseline_performance/dashboard.png")

## 5. Summary Statistics
# Create a comprehensive summary table
summary_data = []

for _, row in df.iterrows():
    speedup = row['throughput'] / df.iloc[0]['throughput']
    ideal_speedup = row['cores']
    efficiency = (speedup / ideal_speedup) * 100 if ideal_speedup > 0 else 0
    per_core_eff = (row['per_core_throughput'] / df.iloc[0]['per_core_throughput']) * 100
    
    summary_data.append({
        'Cores': int(row['cores']),
        'Throughput (txns/s)': f"{row['throughput']:,.0f}",
        'Per-Core (txns/s/core)': f"{row['per_core_throughput']:,.0f}",
        'Speedup': f"{speedup:.2f}x",
        'Efficiency (%)': f"{efficiency:.1f}",
        'Avg Latency (ms)': f"{row['avg_latency_ms']:.3f}",
        'Abort Rate (%)': f"{row['abort_rate']:.2f}",
        'Committed': f"{row['committed']:,}",
        'Aborted': f"{int(row['aborted']):,}"
    })

summary_df = pd.DataFrame(summary_data)
print("\n" + "="*100)
print("COMPREHENSIVE PERFORMANCE SUMMARY")
print("="*100)
print(summary_df.to_string(index=False))
print("="*100)

# Key insights
print("\n" + "="*100)
print("KEY INSIGHTS")
print("="*100)
max_throughput_row = df.loc[df['throughput'].idxmax()]
min_latency_row = df.loc[df['avg_latency_ms'].idxmin()]
max_efficiency_row = df.loc[df['per_core_throughput'].idxmax()]

print(f"✅ Peak Throughput: {max_throughput_row['throughput']:,.0f} txns/s at {int(max_throughput_row['cores'])} cores")
print(f"✅ Lowest Latency: {min_latency_row['avg_latency_ms']:.3f} ms at {int(min_latency_row['cores'])} cores")
print(f"✅ Best Per-Core Efficiency: {max_efficiency_row['per_core_throughput']:,.0f} txns/s/core at {int(max_efficiency_row['cores'])} cores")

total_speedup = df.iloc[-1]['throughput'] / df.iloc[0]['throughput']
ideal_total_speedup = df.iloc[-1]['cores']
overall_efficiency = (total_speedup / ideal_total_speedup) * 100
print(f"✅ Overall Scaling: {total_speedup:.2f}x speedup ({overall_efficiency:.1f}% of ideal) from 1 to {int(df.iloc[-1]['cores'])} cores")

print("="*100)
print("\n✅ Visualization complete! All plots saved to results/baseline_performance/")


#!/usr/bin/env python3
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone
import pandas as pd
from pathlib import Path
import numpy as np

try:
    from scipy.interpolate import interp1d
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

def load_iperf_data(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def extract_throughput_data(data):
    # Get test start timestamp
    start_timestamp = data['start']['timestamp']['timesecs']
    start_datetime = datetime.fromtimestamp(start_timestamp, tz=timezone.utc)
    
    # Extract intervals data
    intervals = data['intervals']
    
    # Initialize data structures
    timestamps = []
    stream_throughputs = {}  # socket_id -> list of throughputs
    combined_throughputs = []
    
    for interval in intervals:
        # Calculate absolute timestamp for this interval
        interval_start = interval['sum']['start']
        interval_datetime = datetime.fromtimestamp(start_timestamp + interval_start, tz=timezone.utc)
        timestamps.append(interval_datetime)
        
        # Get combined throughput (sum of all streams)
        combined_gbps = interval['sum']['bits_per_second'] / 1e9
        combined_throughputs.append(combined_gbps)
        
        # Get individual stream throughputs
        for stream in interval['streams']:
            socket_id = stream['socket']
            stream_gbps = stream['bits_per_second'] / 1e9
            
            if socket_id not in stream_throughputs:
                stream_throughputs[socket_id] = []
            stream_throughputs[socket_id].append(stream_gbps)
    
    return timestamps, stream_throughputs, combined_throughputs

def plot_throughput(timestamps, stream_throughputs, combined_throughputs):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    
    # Plot individual streams
    colors = plt.cm.tab20(range(len(stream_throughputs)))
    for i, (socket_id, throughputs) in enumerate(sorted(stream_throughputs.items())):
        ax1.plot(timestamps, throughputs, label=f'Stream {socket_id}', 
                color=colors[i], alpha=0.7, linewidth=1)
    
    ax1.set_ylabel('Throughput (Gbps)')
    ax1.set_title('iperf3 TCP Performance - Individual Streams')
    ax1.grid(True, alpha=0.3)
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    
    # Plot combined throughput
    ax2.plot(timestamps, combined_throughputs, 'b-', linewidth=1, label='Combined (16 streams)')
    ax2.set_ylabel('Throughput (Gbps)')
    ax2.set_xlabel('Time')
    ax2.set_title('iperf3 TCP Performance - Combined Throughput')
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    
    # Format x-axis
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    ax2.xaxis.set_major_locator(mdates.SecondLocator(interval=2))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    return fig

def load_multiple_nic_data(results_dir):
    """Load iperf3 results from multiple NIC files in a directory"""
    results_dir = Path(results_dir)
    nic_data = {}
    
    # Find all client_*.json files
    json_files = sorted(results_dir.glob('client_*.json'))
    
    for json_file in json_files:
        # Extract NIC number from filename (e.g., client_0_results.json -> 0)
        nic_id = json_file.stem.split('_')[1]
        nic_data[f'NIC_{nic_id}'] = load_iperf_data(json_file)
    
    return nic_data

def extract_multi_nic_data(nic_data):
    """Extract throughput data for multiple NICs"""
    multi_nic_results = {}
    
    for nic_name, data in nic_data.items():
        timestamps, stream_throughputs, combined_throughputs = extract_throughput_data(data)
        multi_nic_results[nic_name] = {
            'timestamps': timestamps,
            'stream_throughputs': stream_throughputs,
            'combined_throughputs': combined_throughputs
        }
    
    return multi_nic_results

def plot_all_streams_all_nics(multi_nic_results):
    """Plot all streams for each NIC on separate subplots (handles variable stream counts)"""
    with plt.style.context('seaborn-v0_8-colorblind'):
        num_nics = len(multi_nic_results)
        fig, axes = plt.subplots(num_nics, 1, figsize=(15, 4*num_nics), sharex=True)
        
        if num_nics == 1:
            axes = [axes]
        
        # Determine max number of streams across all NICs for consistent coloring
        max_streams = max(len(results['stream_throughputs']) for results in multi_nic_results.values())
        colors = plt.cm.tab10(np.linspace(0, 1, max(max_streams, 10)))
        
        for idx, (nic_name, results) in enumerate(sorted(multi_nic_results.items())):
            ax = axes[idx]
            timestamps = results['timestamps']
            stream_throughputs = results['stream_throughputs']
            num_streams = len(stream_throughputs)
            
            for i, (socket_id, throughputs) in enumerate(sorted(stream_throughputs.items())):
                ax.plot(timestamps, throughputs, label=f'Stream {i+1}', 
                       color=colors[i % len(colors)], alpha=0.8, linewidth=1)
            
            ax.set_ylabel('Throughput (Gbps)')
            ax.set_title(f'{nic_name} - All {num_streams} Individual Stream{"s" if num_streams != 1 else ""}')
            
            # Adjust legend based on number of streams
            if num_streams <= 8:
                ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8, ncol=1)
            else:
                ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=7, ncol=2)
        
        # Format x-axis on bottom plot
        axes[-1].set_xlabel('Time')
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        axes[-1].xaxis.set_major_locator(mdates.SecondLocator(interval=30))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        return fig

def plot_individual_nic_throughput(multi_nic_results):
    """Plot the combined throughput for each individual NIC (from interval['sum']['bits_per_second'])"""
    with plt.style.context('seaborn-v0_8-colorblind'):
        fig, ax = plt.subplots(1, 1, figsize=(12, 6))
        
        colors = plt.cm.tab10(np.linspace(0, 1, len(multi_nic_results)))
        
        # Determine stream counts for title
        stream_counts = [len(results['stream_throughputs']) for results in multi_nic_results.values()]
        unique_counts = set(stream_counts)
        
        if len(unique_counts) == 1:
            stream_desc = f"Sum of {list(unique_counts)[0]} stream{'s' if list(unique_counts)[0] != 1 else ''} per NIC"
        else:
            stream_desc = f"Sum of streams per NIC (varies: {sorted(unique_counts)})"
        
        for idx, (nic_name, results) in enumerate(sorted(multi_nic_results.items())):
            timestamps = results['timestamps']
            combined_throughputs = results['combined_throughputs']
            num_streams = len(results['stream_throughputs'])
            
            ax.plot(timestamps, combined_throughputs, 
                   label=f'{nic_name} Total ({num_streams} stream{"s" if num_streams != 1 else ""})', 
                   color=colors[idx], linewidth=1)
        
        ax.set_ylabel('Throughput (Gbps)')
        ax.set_xlabel('Time')
        ax.set_title(f'Individual NIC Throughput ({stream_desc})')
        ax.legend(fontsize=10)
        
        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        ax.xaxis.set_major_locator(mdates.SecondLocator(interval=30))
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        return fig

def align_and_combine_nics(multi_nic_results, interpolation_interval=1.0):
    """Properly align timestamps and interpolate data for combining NICs"""
    if not SCIPY_AVAILABLE:
        raise ImportError("scipy is required for proper timestamp alignment")
    
    # Find common time range in seconds since epoch
    all_start_times = []
    all_end_times = []
    
    for results in multi_nic_results.values():
        timestamps = results['timestamps']
        timestamp_seconds = [t.timestamp() for t in timestamps]
        all_start_times.append(min(timestamp_seconds))
        all_end_times.append(max(timestamp_seconds))
    
    common_start = max(all_start_times)
    common_end = min(all_end_times)
    
    # Create common time grid
    common_time_seconds = np.arange(common_start, common_end, interpolation_interval)
    common_timestamps = [datetime.fromtimestamp(t, tz=timezone.utc) for t in common_time_seconds]
    
    # Interpolate each NIC's data to common grid
    aligned_data = {}
    
    for nic_name, results in multi_nic_results.items():
        timestamps = results['timestamps']
        combined_throughputs = results['combined_throughputs']
        
        # Convert to seconds for interpolation
        timestamp_seconds = np.array([t.timestamp() for t in timestamps])
        throughput_array = np.array(combined_throughputs)
        
        # Only interpolate within the valid range
        valid_start = max(min(timestamp_seconds), common_start)
        valid_end = min(max(timestamp_seconds), common_end)
        
        # Filter common grid to valid range for this NIC
        valid_mask = (common_time_seconds >= valid_start) & (common_time_seconds <= valid_end)
        valid_common_times = common_time_seconds[valid_mask]
        valid_common_timestamps = [common_timestamps[i] for i in range(len(common_timestamps)) if valid_mask[i]]
        
        if len(valid_common_times) > 0:
            # Interpolate
            interp_func = interp1d(timestamp_seconds, throughput_array, 
                                 kind='linear', bounds_error=False, fill_value=0)
            interpolated_throughputs = interp_func(valid_common_times)
            
            aligned_data[nic_name] = {
                'timestamps': valid_common_timestamps,
                'throughputs': interpolated_throughputs.tolist()
            }
    
    return aligned_data, common_timestamps, common_time_seconds

def plot_total_combined_all_nics(multi_nic_results):
    """Plot total combined throughput across all NICs with proper timestamp alignment"""
    with plt.style.context('seaborn-v0_8-colorblind'):
        if not SCIPY_AVAILABLE:
            print("Warning: scipy not available. Using simplified alignment (may be inaccurate)")
            # Fallback to simpler method - just plot individual NICs
            return plot_individual_nic_throughput(multi_nic_results)
        
        aligned_data, common_timestamps, common_time_seconds = align_and_combine_nics(multi_nic_results)
        
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        # Find the common time range across all NICs
        min_length = min(len(data['throughputs']) for data in aligned_data.values())
        total_throughput = np.zeros(min_length)
        plot_timestamps = None
        
        # Accumulate total across all NICs
        for nic_name, data in aligned_data.items():
            timestamps = data['timestamps'][:min_length]  # Trim to common length
            throughputs = data['throughputs'][:min_length]
            
            # Accumulate for total (now properly aligned)
            total_throughput += np.array(throughputs)
            if plot_timestamps is None:
                plot_timestamps = timestamps
        
        # Plot total combined
        if plot_timestamps is not None and len(total_throughput) > 0:
            num_nics = len(multi_nic_results)
            ax.plot(plot_timestamps, total_throughput, 
                    linewidth=1, label=f'Total All {num_nics} NICs Combined')
            
            # Add some statistics as text
            avg_total = np.mean(total_throughput)
            max_total = np.max(total_throughput)
            ax.text(0.02, 0.95, f'Average: {avg_total:.1f} Gbps\nPeak: {max_total:.1f} Gbps', 
                    transform=ax.transAxes, fontsize=12, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
            
            ax.set_ylabel('Throughput (Gbps)', fontsize=12)
            ax.set_xlabel('Time', fontsize=12)
            ax.set_title(f'Total Combined Throughput (All {num_nics} NICs - Time Aligned)', fontsize=14, fontweight='bold')
            ax.legend(fontsize=12)
            
            # Format x-axis
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax.xaxis.set_major_locator(mdates.SecondLocator(interval=30))
            plt.xticks(rotation=45)
        
        plt.tight_layout()
        return fig
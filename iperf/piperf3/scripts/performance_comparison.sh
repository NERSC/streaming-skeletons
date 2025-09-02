#!/bin/bash

# Performance comparison script for different iperf3 configurations
# Tests various parameters to find optimal settings

set -e

if [ $# -lt 1 ]; then
    echo "Usage: $0 <server_host> [output_dir]"
    echo "Example: $0 node001.cluster.local ./performance_comparison"
    exit 1
fi

SERVER_HOST=$1
OUTPUT_DIR=${2:-"./performance_comparison_$(date +%Y%m%d_%H%M%S)"}

echo "Performance Comparison Test"
echo "=========================="
echo "Server: $SERVER_HOST"
echo "Output: $OUTPUT_DIR"
echo ""

mkdir -p $OUTPUT_DIR

# Test parameters to vary
PARALLEL_STREAMS=(1 2 4 8 16)
BITRATES=("1G" "5G" "10G" "25G" "40G")
PROTOCOLS=("tcp" "udp")
DURATIONS=(10 30 60)

# TCP-specific parameters
TCP_ALGORITHMS=("cubic" "bbr" "reno")
WINDOW_SIZES=("64K" "128K" "256K" "512K")

# Test counter
TEST_NUM=0
TOTAL_TESTS=$((${#PARALLEL_STREAMS[@]} * ${#BITRATES[@]} * 2 * ${#DURATIONS[@]} + ${#TCP_ALGORITHMS[@]} * ${#WINDOW_SIZES[@]}))

echo "Planning $TOTAL_TESTS tests..."
echo ""

# Create base configuration
cat > $OUTPUT_DIR/base_config.yaml << EOF
name: "performance_comparison"
description: "Systematic performance testing with varying parameters"
version: "1.0"
tags: ["performance", "comparison", "optimization"]

client_config:
  server_host: "$SERVER_HOST"
  port: 5201
  json_output: true
  verbose: false
  get_server_output: true
  omit: 3

output_directory: "$OUTPUT_DIR"
EOF

# Function to run a test
run_test() {
    local test_name=$1
    local config_file=$2
    local test_output=$3
    
    TEST_NUM=$((TEST_NUM + 1))
    echo "[$TEST_NUM/$TOTAL_TESTS] Running: $test_name"
    
    mkdir -p $test_output
    
    # Run the test
    if uv run piperf3 client $SERVER_HOST --config $config_file --output-dir $test_output 2>/dev/null; then
        echo "  ✓ Completed successfully"
    else
        echo "  ✗ Failed"
    fi
    
    sleep 1  # Brief pause between tests
}

# Test 1: Parallel stream scaling
echo "=== Testing Parallel Stream Scaling ==="
for streams in "${PARALLEL_STREAMS[@]}"; do
    for protocol in "${PROTOCOLS[@]}"; do
        for duration in "${DURATIONS[@]}"; do
            test_name="streams_${streams}_${protocol}_${duration}s"
            config_file="$OUTPUT_DIR/config_$test_name.yaml"
            test_output="$OUTPUT_DIR/results/$test_name"
            
            # Create test-specific config
            cp $OUTPUT_DIR/base_config.yaml $config_file
            cat >> $config_file << EOF
client_config:
  parallel_streams: $streams
  protocol: "$protocol"
  time: $duration
  bitrate: "10G"
EOF
            
            run_test "$test_name" "$config_file" "$test_output"
        done
    done
done

# Test 2: Bitrate scaling (TCP only, 30s, 4 streams)
echo ""
echo "=== Testing Bitrate Scaling ==="
for bitrate in "${BITRATES[@]}"; do
    test_name="bitrate_${bitrate}_tcp_30s_4streams"
    config_file="$OUTPUT_DIR/config_$test_name.yaml"
    test_output="$OUTPUT_DIR/results/$test_name"
    
    cp $OUTPUT_DIR/base_config.yaml $config_file
    cat >> $config_file << EOF
client_config:
  parallel_streams: 4
  protocol: "tcp"
  time: 30
  bitrate: "$bitrate"
EOF
    
    run_test "$test_name" "$config_file" "$test_output"
done

# Test 3: TCP Congestion Algorithm Comparison
echo ""
echo "=== Testing TCP Congestion Algorithms ==="
for algo in "${TCP_ALGORITHMS[@]}"; do
    for window in "${WINDOW_SIZES[@]}"; do
        test_name="tcp_${algo}_window_${window}"
        config_file="$OUTPUT_DIR/config_$test_name.yaml"
        test_output="$OUTPUT_DIR/results/$test_name"
        
        cp $OUTPUT_DIR/base_config.yaml $config_file
        cat >> $config_file << EOF
client_config:
  parallel_streams: 4
  protocol: "tcp"
  time: 30
  bitrate: "10G"
  congestion_algorithm: "$algo"
  window: "$window"
  no_delay: true
EOF
        
        run_test "$test_name" "$config_file" "$test_output"
    done
done

echo ""
echo "=== All Tests Completed ==="

# Generate comprehensive analysis
echo "Generating performance analysis..."

# Collect all results for plotting
RESULT_DIRS=($(find $OUTPUT_DIR/results -mindepth 1 -maxdepth 1 -type d))

if [ ${#RESULT_DIRS[@]} -gt 0 ]; then
    uv run piperf3 plot-results "${RESULT_DIRS[@]}" \
        --output-dir $OUTPUT_DIR/analysis \
        --title "Performance Comparison Analysis"
    
    # Create detailed CSV for analysis
    echo "Creating detailed CSV analysis..."
    uv run python << EOF
import sys
sys.path.append('src')
from piperf3.plotting import IperfPlotter
from pathlib import Path

# Load all results and create CSV
result_dirs = [Path(d) for d in "${RESULT_DIRS[@]}".split()]
results = []

for result_dir in result_dirs:
    json_file = result_dir / "results.json"
    if json_file.exists():
        import json
        from piperf3.models import IperfResult
        
        with open(json_file) as f:
            json_data = json.load(f)
        
        result = IperfResult(
            environment_name=result_dir.name,
            run_id=result_dir.name,
            start_time=None,
            config_used=None,
            output_directory=result_dir,
            json_results=json_data
        )
        results.append(result)

if results:
    IperfPlotter.save_results_csv(results, Path("$OUTPUT_DIR/analysis/detailed_results.csv"))
    print(f"Saved detailed analysis to: $OUTPUT_DIR/analysis/detailed_results.csv")
EOF

else
    echo "Warning: No results found for analysis"
fi

# Create summary report
cat > $OUTPUT_DIR/performance_summary.md << EOF
# Performance Comparison Report

**Server:** $SERVER_HOST  
**Date:** $(date)  
**Total Tests:** $TEST_NUM  
**Output Directory:** $OUTPUT_DIR

## Test Categories

### 1. Parallel Stream Scaling
- Streams tested: ${PARALLEL_STREAMS[*]}
- Protocols: ${PROTOCOLS[*]}
- Durations: ${DURATIONS[*]}s

### 2. Bitrate Scaling  
- Bitrates tested: ${BITRATES[*]}
- Fixed parameters: TCP, 30s, 4 streams

### 3. TCP Optimization
- Congestion algorithms: ${TCP_ALGORITHMS[*]}
- Window sizes: ${WINDOW_SIZES[*]}

## Results

- **Raw data:** \`$OUTPUT_DIR/results/\`
- **Plots:** \`$OUTPUT_DIR/analysis/\`
- **CSV data:** \`$OUTPUT_DIR/analysis/detailed_results.csv\`

## Recommendations

Review the generated plots and CSV data to identify optimal configurations for your network environment.

EOF

echo ""
echo "Performance comparison completed!"
echo "Results: $OUTPUT_DIR"
echo "Summary: $OUTPUT_DIR/performance_summary.md"
echo "Plots: $OUTPUT_DIR/analysis/"

#!/bin/bash
#SBATCH --job-name=iperf3_matrix_test  
#SBATCH --nodes=4
#SBATCH --ntasks-per-node=1
#SBATCH --time=01:00:00
#SBATCH --output=iperf3_matrix_%j.out
#SBATCH --error=iperf3_matrix_%j.err

# Matrix testing script - tests all node pairs
# Usage: sbatch run_matrix_test.sh

set -e

# Load environment
module load python/3.12
# Assume uv is available - if not, use: pip install uv

# Get all nodes
NODES=($(scontrol show hostname $SLURM_NODELIST))
NUM_NODES=${#NODES[@]}

echo "Running iperf3 matrix test with $NUM_NODES nodes:"
printf '%s\n' "${NODES[@]}"

# Create base output directory
BASE_OUTPUT="results/matrix_job_${SLURM_JOB_ID}_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BASE_OUTPUT

# Test configuration
TEST_DURATION=30
TEST_PARALLEL=4
TEST_BITRATE="10G"

echo "Test configuration:"
echo "  Duration: ${TEST_DURATION}s"
echo "  Parallel streams: $TEST_PARALLEL"
echo "  Bitrate: $TEST_BITRATE"
echo ""

# Matrix testing - each node talks to every other node
for ((i=0; i<$NUM_NODES; i++)); do
    for ((j=0; j<$NUM_NODES; j++)); do
        if [ $i -ne $j ]; then
            SERVER_NODE=${NODES[$i]}
            CLIENT_NODE=${NODES[$j]}
            
            echo "Testing: $CLIENT_NODE -> $SERVER_NODE"
            
            # Create test-specific output directory
            TEST_OUTPUT="$BASE_OUTPUT/${CLIENT_NODE}_to_${SERVER_NODE}"
            mkdir -p $TEST_OUTPUT
            
            # Start server
            srun --nodes=1 --ntasks=1 --nodelist=$SERVER_NODE \
                uv run piperf3 server \
                --port 5201 \
                --json \
                --one-off \
                --output-dir $TEST_OUTPUT/server &
            
            SERVER_PID=$!
            sleep 3  # Give server time to start
            
            # Run client
            srun --nodes=1 --ntasks=1 --nodelist=$CLIENT_NODE \
                uv run piperf3 client $SERVER_NODE \
                --port 5201 \
                --time $TEST_DURATION \
                --parallel $TEST_PARALLEL \
                --bitrate $TEST_BITRATE \
                --json \
                --output-dir $TEST_OUTPUT/client \
                --title "Matrix Test: $CLIENT_NODE -> $SERVER_NODE"
            
            # Clean up server
            wait $SERVER_PID 2>/dev/null || true
            
            echo "  Completed: $CLIENT_NODE -> $SERVER_NODE"
            sleep 2  # Brief pause between tests
        fi
    done
done

echo ""
echo "All matrix tests completed!"

# Generate comprehensive analysis
echo "Generating matrix analysis plots..."

# Collect all client results
find $BASE_OUTPUT -name "client" -type d | while read client_dir; do
    find $client_dir -name "results.json" -type f
done > $BASE_OUTPUT/all_results.txt

if [ -s $BASE_OUTPUT/all_results.txt ]; then
    # Extract result directories for plotting
    RESULT_DIRS=($(dirname $(cat $BASE_OUTPUT/all_results.txt)))
    
    uv run piperf3 plot-results "${RESULT_DIRS[@]}" \
        --output-dir $BASE_OUTPUT/analysis \
        --title "Network Performance Matrix (Job $SLURM_JOB_ID)"
    
    echo "Matrix analysis saved to: $BASE_OUTPUT/analysis"
else
    echo "Warning: No results found for analysis"
fi

# Create summary report
echo "Generating summary report..."
cat > $BASE_OUTPUT/test_summary.txt << EOF
Iperf3 Network Performance Matrix Test
======================================

Job ID: $SLURM_JOB_ID
Date: $(date)
Nodes: $NUM_NODES
Node List: ${NODES[*]}

Test Configuration:
- Duration: ${TEST_DURATION} seconds
- Parallel Streams: $TEST_PARALLEL
- Target Bitrate: $TEST_BITRATE
- Total Tests: $((NUM_NODES * (NUM_NODES - 1)))

Results Directory: $BASE_OUTPUT
EOF

echo ""
echo "Matrix test job completed successfully!"
echo "Results saved to: $BASE_OUTPUT"
echo "Summary: $BASE_OUTPUT/test_summary.txt"

#!/bin/bash
#SBATCH --job-name=iperf3_node_to_node
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --time=00:10:00
#SBATCH --output=iperf3_test_%j.out
#SBATCH --error=iperf3_test_%j.err

# Example SLURM script for running iperf3 tests between two nodes
# Usage: sbatch run_node_to_node.sh

set -e

# Load environment
module load python/3.12
# Assume uv is available - if not, use: pip install uv

# Get nodes
NODES=($(scontrol show hostname $SLURM_NODELIST))
SERVER_NODE=${NODES[0]}
CLIENT_NODE=${NODES[1]}

echo "Running iperf3 test between nodes:"
echo "Server: $SERVER_NODE"
echo "Client: $CLIENT_NODE"

# Create output directory
OUTPUT_DIR="results/job_${SLURM_JOB_ID}_$(date +%Y%m%d_%H%M%S)"
mkdir -p $OUTPUT_DIR

# Start server on first node in background
echo "Starting server on $SERVER_NODE..."
srun --nodes=1 --ntasks=1 --nodelist=$SERVER_NODE \
    uv run piperf3 server \
    --port 5201 \
    --json \
    --verbose \
    --output-dir $OUTPUT_DIR/server \
    --daemon &

SERVER_PID=$!
sleep 5  # Give server time to start

# Run client on second node
echo "Running client on $CLIENT_NODE..."
srun --nodes=1 --ntasks=1 --nodelist=$CLIENT_NODE \
    uv run piperf3 client $SERVER_NODE \
    --port 5201 \
    --time 30 \
    --parallel 4 \
    --bitrate 10G \
    --json \
    --verbose \
    --plot \
    --output-dir $OUTPUT_DIR/client

# Wait for server to finish and clean up
sleep 2
kill $SERVER_PID 2>/dev/null || true

echo "Test completed. Results in: $OUTPUT_DIR"

# Generate summary plots
echo "Generating summary plots..."
uv run piperf3 plot-results $OUTPUT_DIR/client/*/  \
    --output-dir $OUTPUT_DIR/plots \
    --title "Node-to-Node Performance Test (Job $SLURM_JOB_ID)"

echo "Job completed successfully!"

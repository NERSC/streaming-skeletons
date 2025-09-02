#!/bin/bash
#SBATCH --job-name=iperf-node-node
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --qos=debug
#SBATCH --time=00:30:00
#SBATCH --constraint=cpu
#SBATCH --account=nstaff
#SBATCH --output=%j.out
#SBATCH --exclusive

CURRENT_DIR=$(pwd)
today_datetime=$(date +%Y-%m-%d_%H-%M-%S)
echo "Node-to-Node benchmark started at: $today_datetime"
RESULTS_DIR="$CURRENT_DIR/out/node_node_$today_datetime"
mkdir -p "$RESULTS_DIR"
cd "$RESULTS_DIR"

# Save a copy of this script
cp "$0" "$RESULTS_DIR/node_node.sh"

# Configuration for server and client execution methods
SERVER_METHOD="srun"
CLIENT_METHOD="srun"

# Get the hostnames of the allocated nodes
nodes=$(scontrol show hostnames "$SLURM_NODELIST")
nodes_array=($nodes)

# Assign roles
server_node=${nodes_array[0]}
server_node_hostname=${server_node}.chn.perlmutter.nersc.gov
client_node=${nodes_array[1]}

echo "Server method: $SERVER_METHOD"
echo "Server node: $server_node"
echo "Server node hostname: $server_node_hostname"
echo "Client method: $CLIENT_METHOD"
echo "Client node: $client_node"

# Destination IP address
DEST_IP="$server_node_hostname"

# Source common functions
source "$CURRENT_DIR/common.sh"
cp "$CURRENT_DIR/common.sh" "$RESULTS_DIR/"

# Benchmark 5: nic numa on both
echo "=== Benchmark 5: nic numa on both ==="
start_server true 2 5
start_client true 2 5
wait_and_cleanup


echo "Node-to-Node benchmark finished."
mv "$CURRENT_DIR/$SLURM_JOB_ID.out" "$RESULTS_DIR/"
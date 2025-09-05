#!/bin/bash
#SBATCH --job-name=piperf-node-node
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH --qos=debug
#SBATCH --time=00:30:00
#SBATCH --constraint=cpu
#SBATCH --account=nstaff
#SBATCH --output=%j.out
#SBATCH --exclusive

# Get hostnames
nodes=$(scontrol show hostnames "$SLURM_NODELIST")
nodes_array=($nodes)
server_node=${nodes_array[0]}
server_node_hostname=${server_node}.chn.perlmutter.nersc.gov
client_node=${nodes_array[1]}

CPU_NODE_NIC_NUMA=2

srun --nodes=1 --ntasks=1 -w ${server_node} numactl --cpunodebind=${CPU_NODE_NIC_NUMA} \
    uv run piperf3 server &
SERVER_PID=$!

srun --nodes=1 --ntasks=1 -w ${client_node} numactl --cpunodebind=${CPU_NODE_NIC_NUMA} \
    uv run piperf3 client ${server_node_hostname}

kill $SERVER_PID 2>/dev/null

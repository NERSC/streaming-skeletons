#!/bin/bash
#SBATCH --job-name=piperf-gh
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=1
#SBATCH -p gh-dev
#SBATCH --time=00:15:00
#SBATCH -A CDA24017
#SBATCH --output=%j.out
#SBATCH --exclusive

# Get hostnames
nodes=$(scontrol show hostnames "$SLURM_NODELIST")
nodes_array=($nodes)
server_node=${nodes_array[0]}
client_node=${nodes_array[1]}

CPU_NODE_NIC_NUMA=0

# Get the InfiniBand IP (second IP from hostname -I)
server_ib_ip=$(srun --nodes=1 --ntasks=1 -w ${server_node} hostname -I | awk '{print $2}')

srun --nodes=1 --ntasks=1 -w ${server_node} numactl --cpunodebind=${CPU_NODE_NIC_NUMA} \
    uv run piperf3 server &
SERVER_PID=$!

sleep 5

srun --nodes=1 --ntasks=1 -w ${client_node} numactl --cpunodebind=${CPU_NODE_NIC_NUMA} \
    uv run piperf3 client ${server_ib_ip}

kill $SERVER_PID 2>/dev/null


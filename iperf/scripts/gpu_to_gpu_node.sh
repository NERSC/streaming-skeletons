#!/bin/bash
#SBATCH --job-name=iperf-gpu-to-gpu-node
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=4
#SBATCH --qos=debug
#SBATCH --time=00:30:00
#SBATCH --constraint=gpu
#SBATCH --account=nstaff
#SBATCH --output=%j.out
#SBATCH --exclusive

# =============================================================================
# GPU-to-GPU Node Network Performance Testing Script
# =============================================================================
# This script runs iperf3 tests between two GPU nodes using SLURM.
# It launches 4 iperf3 server processes on the first node and 4 client 
# processes on the second node. Each process is bound to the closest GPU 
# and uses a dedicated NIC (hsn0-hsn3).
#
# Usage:
#   Interactive: salloc -q interactive -t 30 -A <account> -N 2 -C 'gpu' 
#                then ./gpu_to_gpu_node.sh
#   Batch:       sbatch -q debug -t 30 -A <account> -N 2 -C 'gpu' gpu_to_gpu_node.sh
# =============================================================================

set -e  # Exit on any error
set -u  # Exit on undefined variables

# =============================================================================
# Configuration
# =============================================================================
readonly IPERF3_BIN="/global/homes/a/asnaylor/tmp/nersc_iperf3_tests/iperf-3.19.1/src/iperf3"
readonly IPERF3_PORT=5201
readonly TEST_DURATION=300
readonly TASKS_PER_NODE=4
readonly SERVER_STARTUP_DELAY=10

readonly CLIENT_ARGS="-t ${TEST_DURATION} --json -P 16"
readonly SERVER_ARGS="-s"
readonly OUTPUT_DIR="./iperf_results_$(date +%Y%m%d_%H%M%S)"

# SLURM resource configuration
readonly CPUS_PER_TASK=16
readonly THREADS_PER_CORE=1

# Global variables for cleanup
SERVER_SRUN_PID=""
SERVER_NODE=""
CLIENT_NODE=""

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo "[INFO] $(date '+%H:%M:%S') $*"
}

log_error() {
    echo "[ERROR] $(date '+%H:%M:%S') $*" >&2
}

log_warn() {
    echo "[WARN] $(date '+%H:%M:%S') $*" >&2
}

# =============================================================================
# Cleanup Functions
# =============================================================================

cleanup_servers() {
    if [[ -n "$SERVER_SRUN_PID" ]]; then
        log_info "Terminating server processes (PID: $SERVER_SRUN_PID)"
        
        # Kill the srun process - this will terminate all child iperf3 processes
        if kill "$SERVER_SRUN_PID" 2>/dev/null; then
            # Wait briefly for graceful termination
            local count=0
            while kill -0 "$SERVER_SRUN_PID" 2>/dev/null && [[ $count -lt 5 ]]; do
                sleep 1
                ((count++))
            done
            
            # Force kill if still running
            if kill -0 "$SERVER_SRUN_PID" 2>/dev/null; then
                log_warn "Force killing server processes"
                kill -9 "$SERVER_SRUN_PID" 2>/dev/null || true
            fi
        fi
        
    fi
}

cleanup_on_exit() {
    # Only cleanup if we haven't already done so
    if [[ -n "$SERVER_SRUN_PID" ]]; then
        cleanup_servers
    fi
}

cleanup_on_signal() {
    log_warn "Received termination signal, cleaning up..."
    cleanup_servers
    exit 130
}
# Set up signal handlers for cleanup
trap cleanup_on_exit EXIT
trap cleanup_on_signal SIGINT SIGTERM

# =============================================================================
# Core Functions
# =============================================================================

create_output_directory() {
    mkdir -p "$OUTPUT_DIR"
    log_info "Created output directory: $OUTPUT_DIR"
}

get_node_assignments() {
    SERVER_NODE=$(scontrol show hostname "$SLURM_JOB_NODELIST" | head -n1)
    CLIENT_NODE=$(scontrol show hostname "$SLURM_JOB_NODELIST" | tail -n1)
    
    log_info "Server node: $SERVER_NODE"
    log_info "Client node: $CLIENT_NODE"
}

validate_node_assignment() {
    if [[ "$SERVER_NODE" == "$CLIENT_NODE" ]]; then
        log_error "Need 2 different nodes for testing"
        exit 1
    fi
    log_info "Node assignment validated successfully"
}

start_iperf_servers() {
    log_info "Starting $TASKS_PER_NODE iperf3 servers on $SERVER_NODE..."
    
    # Export variables for srun environment
    export IPERF3_BIN SERVER_ARGS IPERF3_PORT
    
    srun --nodes=1 --ntasks="$TASKS_PER_NODE" --nodelist="$SERVER_NODE" \
         --gpus-per-task=1 --gpu-bind=closest \
         --cpus-per-task="$CPUS_PER_TASK" --threads-per-core="$THREADS_PER_CORE" \
         --label \
         /bin/bash -c '
             INTERFACE="${HOSTNAME}-hsn${SLURM_LOCALID}"
             printf "Starting server on interface: %s [HSN Device NUMA: %s - CPU NUMA: %s]\n" \
                    "$INTERFACE" \
                    "$(cat /sys/class/net/hsn${SLURM_LOCALID}/device/numa_node)" \
                    "$(numactl --show | awk '\''/^cpubind:/ {print $2}'\'')"

             # Set up signal handling for graceful shutdown
             cleanup_server() {
                 echo "Server on $INTERFACE shutting down..."
                 exit 0
             }
             trap cleanup_server SIGTERM SIGINT
             
             $IPERF3_BIN $SERVER_ARGS -p $IPERF3_PORT -B "$INTERFACE"
         ' &
    
    # Store the PID for cleanup
    SERVER_SRUN_PID=$!
    log_info "Server srun started"
    
    log_info "Waiting ${SERVER_STARTUP_DELAY} seconds for servers to initialize..."
    sleep "$SERVER_STARTUP_DELAY"
    
    # Verify servers are running
    if ! kill -0 "$SERVER_SRUN_PID" 2>/dev/null; then
        log_error "Server processes failed to start properly"
        exit 1
    fi
    log_info "Servers initialized successfully"
}

start_iperf_clients() {
    log_info "Starting $TASKS_PER_NODE iperf3 clients on $CLIENT_NODE..."
    
    # Export variables for srun environment
    export SERVER_NODE CLIENT_ARGS OUTPUT_DIR IPERF3_PORT
    
    srun --nodes=1 --ntasks="$TASKS_PER_NODE" --nodelist="$CLIENT_NODE" \
         --gpus-per-task=1 --gpu-bind=closest \
         --cpus-per-task="$CPUS_PER_TASK" --threads-per-core="$THREADS_PER_CORE" \
         --label \
         /bin/bash -c '
             SERVER_INTERFACE="${SERVER_NODE}-hsn${SLURM_LOCALID}"
             CLIENT_INTERFACE="${HOSTNAME}-hsn${SLURM_LOCALID}"
             OUTPUT_FILE="$OUTPUT_DIR/client_${SLURM_LOCALID}_results.json"
             
             printf "Client %s: %s -> %s [HSN Device NUMA: %s - CPU NUMA: %s]\n" \
                    "$SLURM_LOCALID" \
                    "$CLIENT_INTERFACE" \
                    "$SERVER_INTERFACE" \
                    "$(cat /sys/class/net/hsn${SLURM_LOCALID}/device/numa_node)" \
                    "$(numactl --show | awk '\''/^cpubind:/ {print $2}'\'')"

             # Run iperf3 client with error handling
             if $IPERF3_BIN -c "$SERVER_INTERFACE" $CLIENT_ARGS \
                            -p $IPERF3_PORT -B "$CLIENT_INTERFACE" \
                            > "$OUTPUT_FILE" 2>&1; then
                 echo "Client $SLURM_LOCALID completed successfully"
             else
                 echo "Client $SLURM_LOCALID failed" >&2
                 exit 1
             fi
         '
    
    local client_exit_code=$?
    if [[ $client_exit_code -ne 0 ]]; then
        log_error "Some client processes failed (exit code: $client_exit_code)"
        return $client_exit_code
    fi
    
    log_info "All client tests completed successfully"
}

display_results_summary() {
    # Temporarily disable exit on error for result processing
    set +e
    
    log_info "Test completed. Results saved in: $OUTPUT_DIR"
    echo ""
    echo "=== Performance Summary ==="
    
    local total_bandwidth="0"
    local successful_tests=0
    
    for i in $(seq 0 $((TASKS_PER_NODE - 1))); do
        local result_file="$OUTPUT_DIR/client_${i}_results.json"
        
        if [[ -f "$result_file" ]]; then
            local bandwidth
            bandwidth=$(jq -r '.end.sum_received.bits_per_second // "N/A"' "$result_file" 2>/dev/null || echo "N/A")
            
            if [[ "$bandwidth" != "N/A" && "$bandwidth" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                local gbps
                gbps=$(echo "scale=2; $bandwidth / 1000000000" | bc -l 2>/dev/null || echo "N/A")
                echo "  NIC $i (hsn$i): ${gbps} Gbps"
                total_bandwidth=$(echo "$total_bandwidth + $bandwidth" | bc -l 2>/dev/null || echo "0")
                successful_tests=$((successful_tests + 1))
            else
                echo "  NIC $i (hsn$i): Test failed or invalid result"
                log_warn "Check $result_file for error details"
            fi
        else
            echo "  NIC $i (hsn$i): Result file not found"
        fi
    done
    
    if [[ $successful_tests -gt 0 ]]; then
        local total_gbps
        total_gbps=$(echo "scale=2; $total_bandwidth / 1000000000" | bc -l 2>/dev/null || echo "N/A")
        echo ""
        echo "Total Aggregate Bandwidth: ${total_gbps} Gbps ($successful_tests/$TASKS_PER_NODE NICs)"
    else
        log_error "No successful tests completed"
        set -e  # Re-enable exit on error
        return 1
    fi
    
    # Re-enable exit on error
    set -e
}

# =============================================================================
# Main Execution
# =============================================================================

main() {
    log_info "Starting GPU-to-GPU network performance test"
    log_info "Test duration: ${TEST_DURATION} seconds per stream"
    log_info "PID: $$"
    
    create_output_directory
    get_node_assignments
    validate_node_assignment
    
    start_iperf_servers
    start_iperf_clients
    
    # Disable EXIT trap before displaying results to prevent premature cleanup
    trap - EXIT
    
    display_results_summary
    cleanup_servers
    log_info "Script completed successfully"
}

# Execute main function
main "$@"
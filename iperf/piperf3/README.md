# piperf3

A fully-featured Python wrapper for iperf3 designed for high-performance computing environments. This tool provides configuration management, automatic plotting, CLI interface, and comprehensive result tracking for iperf3 network performance testing.

## Features

- 🔧 **Configuration Management**: Support for YAML, TOML, and .env files
- 📊 **Automatic Plotting**: Generate comprehensive performance plots with matplotlib
- 🖥️ **CLI Interface**: Intuitive command-line interface with typer
- ✅ **Full iperf3 Support**: All iperf3 options from the manual page exposed
- 🏷️ **Provenance Tracking**: Track test environments and configurations  
- 📁 **Organized Output**: Results saved to structured directories
- 🧮 **Pydantic Validation**: Type-safe configuration validation
- 🖥️ **HPC Optimized**: Built for supercomputer environments with SLURM integration

## Installation

```bash
# Install from source using uv (recommended)
cd piperf3
uv sync

# Or install with pip
pip install -e .

# Or install dependencies manually
pip install pydantic typer matplotlib pyyaml python-dotenv rich seaborn pandas numpy
```

## Quick Start

### 1. Create Configuration Files

Generate example configuration files:

```bash
uv run piperf3 create-config --output-dir ./config --type all
```

This creates:
- `client_example.yaml` - Client configuration
- `server_example.yaml` - Server configuration  
- `example.env` - Environment variables

### 2. Run iperf3 Server

```bash
# Using configuration file
uv run piperf3 server --config server_example.yaml

# Using command-line options
uv run piperf3 server --port 5201 --verbose --json
```

### 3. Run iperf3 Client

```bash
# Using configuration file  
uv run piperf3 client node001.cluster.local --config client_example.yaml

# Using command-line options
uv run piperf3 client node001.cluster.local --time 30 --parallel 4 --bitrate 10G --plot
```

### 4. Generate Plots from Results

```bash
uv run piperf3 plot-results ./results/test1_* ./results/test2_* --output-dir plots --title "Network Performance Comparison"
```

## Configuration

### YAML Configuration Example

```yaml
name: "hpc_network_test"
description: "High-performance network testing between compute nodes"
version: "1.0"
tags: ["hpc", "network", "performance"]

client_config:
  server_host: "node001.cluster.local"
  port: 5201
  time: 30
  parallel_streams: 4
  bitrate: "10G"
  protocol: "tcp"
  format: "g"
  json_output: true
  reverse: false
  bidir: false
  
  # TCP-specific settings
  no_delay: true
  congestion_algorithm: "cubic"
  window: "128K"
  
  # Performance options
  zerocopy: true
  omit: 3

output_directory: "./results"
```

### Environment Variables

```bash
# Network settings
PIPERF3_SERVER_HOST=node001.cluster.local
PIPERF3_PORT=5201

# Test parameters
PIPERF3_DURATION=30
PIPERF3_BITRATE=10G
PIPERF3_PARALLEL=4
PIPERF3_PROTOCOL=tcp

# Output settings  
PIPERF3_OUTPUT_DIR=./results
PIPERF3_RUN_ID=auto
```

## CLI Commands

### Client Mode
```bash
uv run piperf3 client SERVER [OPTIONS]

Options:
  --config, -c           Configuration file (YAML/TOML)
  --env-file, -e         Environment file (.env)
  --port, -p             Server port
  --time, -t             Test duration (seconds)
  --bitrate, -b          Target bitrate (e.g., '10M', '1G')
  --parallel, -P         Number of parallel streams
  --protocol             Protocol: tcp, udp, or sctp
  --reverse, -R          Reverse test direction  
  --bidir                Bidirectional test
  --json, -J             JSON output
  --output-dir, -o       Output directory
  --plot/--no-plot       Generate plots (default: enabled)
  --verbose, -v          Verbose output
```

### Server Mode
```bash
uv run piperf3 server [OPTIONS]

Options:
  --config, -c           Configuration file (YAML/TOML)
  --env-file, -e         Environment file (.env)
  --port, -p             Server port
  --bind, -B             Bind address
  --daemon, -D           Run as daemon
  --one-off, -1          Handle one client then exit
  --json, -J             JSON output
  --output-dir, -o       Output directory
  --verbose, -v          Verbose output
```

### Plotting
```bash
uv run piperf3 plot-results RESULT_DIRS... [OPTIONS]

Options:
  --output-dir, -o       Output directory for plots
  --title, -t            Title for comparison plots
  --format, -f           Output format (png, pdf, svg)
```

## Result Structure

Each test run creates a structured output directory:

```
results/
├── hpc_test_a1b2c3d4_20240902_143022/
│   ├── command.txt          # Executed iperf3 command
│   ├── stdout.txt           # Raw stdout output
│   ├── stderr.txt           # Raw stderr output  
│   ├── results.json         # Parsed JSON results
│   ├── result_metadata.json # Test metadata and provenance
│   └── plots/              # Generated plots
│       ├── throughput_timeseries.png
│       └── stream_comparison.png
```

## API Usage

```python
from piperf3 import Iperf3Runner, ConfigLoader, IperfPlotter

# Load configuration
config = ConfigLoader.load_environment_config(
    config_file="client.yaml",
    env_file=".env"
)

# Run test
runner = Iperf3Runner()
result = runner.run(config.client_config, config)

# Generate plots
plotter = IperfPlotter() 
plots = plotter.create_dashboard([result], output_dir="plots")

print(f"Test completed: {result.return_code}")
print(f"Results saved to: {result.output_directory}")
```

## License

MIT License - see LICENSE file for details.

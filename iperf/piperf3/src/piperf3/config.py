"""Configuration utilities using Pydantic Settings for iperf3 wrapper."""

from pathlib import Path
from typing import Dict, Any, Optional

from .models import EnvironmentConfig


def load_environment_config(
    config_file: Optional[Path] = None,
    env_file: Optional[Path] = None,
    **override_kwargs,
) -> EnvironmentConfig:
    """
    Load environment configuration using Pydantic Settings.

    Args:
        config_file: Path to YAML/TOML config file (currently unused - will be added in future)
        env_file: Path to .env file
        **override_kwargs: Direct override values

    Returns:
        EnvironmentConfig instance with all settings loaded
    """
    # Prepare kwargs for EnvironmentConfig
    init_kwargs = {}

    # If env_file is specified, pass it to the settings
    if env_file:
        init_kwargs["_env_file"] = env_file

    # Add any direct overrides
    init_kwargs.update(override_kwargs)

    # Let Pydantic Settings handle all the loading automatically
    return EnvironmentConfig(**init_kwargs)


def create_example_configs() -> Dict[str, Any]:
    """Create example configuration files."""

    # Example YAML configuration
    yaml_config = {
        "name": "supercomputer_performance_test",
        "description": "High-performance network testing between compute nodes",
        "version": "1.0",
        "tags": ["hpc", "network", "performance"],
        "server_host": "${PIPERF3_SERVER_HOST:node001}",
        "port": 5201,
        "time": 30,
        "parallel_streams": 4,
        "bitrate": "10G",
        "protocol": "tcp",
        "format": "g",
        "json_output": True,
        "reverse": False,
        "bidir": False,
        "output_directory": "./results",
        "run_id": "${PIPERF3_RUN_ID:auto}",
    }

    # Example server configuration
    server_config = {
        "name": "iperf3_server",
        "description": "Iperf3 server configuration for HPC testing",
        "version": "1.0",
        "port": 5201,
        "json_output": True,
        "verbose": True,
        "format": "g",
        "output_directory": "./server_results",
    }

    # Example .env file content
    env_content = """# Iperf3 Python Wrapper Configuration
# All settings can be set via environment variables with PIPERF3_ prefix

# Basic connection settings
PIPERF3_SERVER_HOST=node001.cluster.local
PIPERF3_PORT=5201

# Test parameters
PIPERF3_DURATION=30
PIPERF3_BITRATE=10G
PIPERF3_PARALLEL=4
PIPERF3_PROTOCOL=tcp
PIPERF3_FORMAT=g

# Output settings
PIPERF3_JSON_OUTPUT=true
PIPERF3_VERBOSE=false
PIPERF3_OUTPUT_DIR=./results
PIPERF3_RUN_ID=auto

# Test configuration
PIPERF3_REVERSE=false
PIPERF3_BIDIR=false

# Metadata
PIPERF3_NAME=hpc_network_test
PIPERF3_TAGS=["hpc", "network", "performance"]
"""

    return {
        "client_example.yaml": yaml_config,
        "server_example.yaml": server_config,
        "example.env": env_content,
    }

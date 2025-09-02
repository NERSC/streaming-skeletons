"""Python wrapper for iperf3 with configuration management and plotting."""

from .models import (
    EnvironmentConfig,
    IperfClientConfig,
    IperfServerConfig,
    IperfResult,
    IperfMode,
    Protocol,
    Format,
    CongestionAlgorithm,
)
from .config import load_environment_config, create_example_configs
from .runner import Iperf3Runner
from .plotting import IperfPlotter
from .cli import app

__version__ = "0.1.0"

__all__ = [
    "EnvironmentConfig",
    "IperfClientConfig",
    "IperfServerConfig",
    "IperfResult",
    "IperfMode",
    "Protocol",
    "Format",
    "CongestionAlgorithm",
    "load_environment_config",
    "create_example_configs",
    "Iperf3Runner",
    "IperfPlotter",
    "main",
]


def main() -> None:
    """Main entry point for the CLI."""
    app()

"""Pydantic models for iperf3 configuration and validation."""

from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class IperfMode(str, Enum):
    """Iperf3 operation modes."""

    CLIENT = "client"
    SERVER = "server"


class Protocol(str, Enum):
    """Network protocols supported by iperf3."""

    TCP = "tcp"
    UDP = "udp"
    SCTP = "sctp"


class Format(str, Enum):
    """Output format options."""

    KBITS = "k"
    MBITS = "m"
    GBITS = "g"
    TBITS = "t"
    KBYTES = "K"
    MBYTES = "M"
    GBYTES = "G"
    TBYTES = "T"


class CongestionAlgorithm(str, Enum):
    """TCP congestion control algorithms."""

    CUBIC = "cubic"
    RENO = "reno"
    BBR = "bbr"
    VEGAS = "vegas"
    WESTWOOD = "westwood"
    BIC = "bic"
    HTCP = "htcp"


class IperfBaseConfig(BaseModel):
    """Base configuration for both client and server."""

    # Connection settings
    port: int = Field(default=5201, ge=1, le=65535, description="Server port")
    bind_address: Optional[str] = Field(default=None, description="Address to bind to")
    bind_device: Optional[str] = Field(
        default=None, description="Network interface to bind to"
    )

    # Protocol settings
    protocol: Protocol = Field(default=Protocol.TCP, description="Transport protocol")
    ipv4_only: bool = Field(default=False, description="Use IPv4 only")
    ipv6_only: bool = Field(default=False, description="Use IPv6 only")

    # Output settings
    format: Optional[Format] = Field(default=None, description="Output format")
    interval: float = Field(
        default=1.0, ge=0, description="Interval between reports (0 to disable)"
    )
    json_output: bool = Field(default=False, description="Output in JSON format")
    json_stream: bool = Field(
        default=False, description="Output in line-delimited JSON"
    )
    verbose: bool = Field(default=False, description="Verbose output")

    # Advanced settings
    cpu_affinity: Optional[Union[int, str]] = Field(
        default=None, description="CPU affinity (n or n,m)"
    )
    pidfile: Optional[Path] = Field(
        default=None, description="Write process ID to file"
    )
    logfile: Optional[Path] = Field(default=None, description="Log output to file")
    force_flush: bool = Field(default=False, description="Force flush output")
    timestamps: Optional[str] = Field(default=None, description="Timestamp format")
    debug: bool = Field(default=False, description="Debug mode")

    # Timeout settings
    rcv_timeout: int = Field(default=120000, ge=0, description="Receive timeout (ms)")
    snd_timeout: Optional[int] = Field(
        default=None, ge=0, description="Send timeout (ms)"
    )

    # Security (if compiled with OpenSSL)
    use_pkcs1_padding: bool = Field(
        default=False, description="Use PKCS1 padding for authentication"
    )

    # MPTCP
    mptcp: bool = Field(default=False, description="Use MPTCP")

    @field_validator("cpu_affinity")
    @classmethod
    def validate_cpu_affinity(cls, v):
        if v is None:
            return v
        if isinstance(v, int):
            return str(v)
        if isinstance(v, str):
            # Validate format: either "n" or "n,m"
            parts = v.split(",")
            if len(parts) > 2:
                raise ValueError("CPU affinity must be 'n' or 'n,m' format")
            for part in parts:
                try:
                    int(part.strip())
                except ValueError:
                    raise ValueError(f"Invalid CPU number: {part}")
        return v

    @model_validator(mode="after")
    def validate_ip_versions(self):
        if self.ipv4_only and self.ipv6_only:
            raise ValueError("Cannot specify both IPv4-only and IPv6-only")
        return self


class IperfServerConfig(IperfBaseConfig):
    """Server-specific configuration."""

    mode: IperfMode = Field(default=IperfMode.SERVER, frozen=True)

    # Server-specific options
    daemon: bool = Field(default=False, description="Run as daemon")
    one_off: bool = Field(default=False, description="Handle one client then exit")
    idle_timeout: Optional[int] = Field(
        default=None, ge=0, description="Idle timeout before exit"
    )
    server_bitrate_limit: Optional[str] = Field(
        default=None, description="Server-side bitrate limit"
    )

    # Authentication (if compiled with OpenSSL)
    rsa_private_key_path: Optional[Path] = Field(
        default=None, description="RSA private key path"
    )
    authorized_users_path: Optional[Path] = Field(
        default=None, description="Authorized users file"
    )
    time_skew_threshold: Optional[int] = Field(
        default=None, ge=0, description="Time skew threshold (seconds)"
    )


class IperfClientConfig(IperfBaseConfig):
    """Client-specific configuration."""

    mode: IperfMode = Field(default=IperfMode.CLIENT, frozen=True)

    # Required for client
    server_host: str = Field(description="Server hostname or IP address")

    # Test parameters
    time: Optional[int] = Field(default=10, ge=1, description="Test duration (seconds)")
    bytes: Optional[str] = Field(
        default=None, description="Number of bytes to transmit"
    )
    blockcount: Optional[str] = Field(
        default=None, description="Number of blocks to transmit"
    )
    bitrate: Optional[str] = Field(default=None, description="Target bitrate")
    pacing_timer: int = Field(
        default=1000, ge=1, description="Pacing timer interval (microseconds)"
    )
    fq_rate: Optional[str] = Field(
        default=None, description="Fair-queueing based pacing rate"
    )

    # Connection settings
    connect_timeout: Optional[int] = Field(
        default=None, ge=1, description="Connection timeout (ms)"
    )
    parallel_streams: int = Field(
        default=1, ge=1, description="Number of parallel streams"
    )
    reverse: bool = Field(default=False, description="Reverse test direction")
    bidir: bool = Field(default=False, description="Bidirectional test")

    # Buffer and packet settings
    length: Optional[str] = Field(default=None, description="Buffer length")
    window: Optional[str] = Field(default=None, description="Socket buffer size")
    set_mss: Optional[int] = Field(
        default=None, ge=1, description="TCP/SCTP maximum segment size"
    )
    no_delay: bool = Field(default=False, description="Disable Nagle's algorithm")

    # Advanced options
    client_port: Optional[int] = Field(
        default=None, ge=1, le=65535, description="Client port"
    )
    tos: Optional[int] = Field(
        default=None, ge=0, le=255, description="IP type of service"
    )
    dscp: Optional[Union[int, str]] = Field(default=None, description="IP DSCP bits")
    flowlabel: Optional[int] = Field(default=None, ge=0, description="IPv6 flow label")

    # File operations
    file_input: Optional[Path] = Field(
        default=None, description="Use file as data source/sink"
    )

    # SCTP-specific
    sctp_streams: Optional[int] = Field(
        default=None, ge=1, description="Number of SCTP streams"
    )
    xbind: Optional[List[str]] = Field(default=None, description="SCTP link bindings")

    # Performance options
    zerocopy: bool = Field(default=False, description="Use zero-copy sending")
    skip_rx_copy: bool = Field(default=False, description="Skip received data copying")
    omit: Optional[int] = Field(
        default=None, ge=0, description="Omit first N seconds from results"
    )

    # Output customization
    title: Optional[str] = Field(default=None, description="Title prefix for output")
    extra_data: Optional[str] = Field(
        default=None, description="Extra data for JSON output"
    )

    # Advanced features
    congestion_algorithm: Optional[CongestionAlgorithm] = Field(
        default=None, description="Congestion control algorithm"
    )
    get_server_output: bool = Field(default=False, description="Retrieve server output")
    udp_counters_64bit: bool = Field(
        default=False, description="Use 64-bit UDP counters"
    )
    repeating_payload: bool = Field(
        default=False, description="Use repeating payload pattern"
    )
    dont_fragment: bool = Field(
        default=False, description="Set IPv4 Don't Fragment bit"
    )

    # Authentication (if compiled with OpenSSL)
    username: Optional[str] = Field(default=None, description="Authentication username")
    password: Optional[str] = Field(default=None, description="Authentication password")
    rsa_public_key_path: Optional[Path] = Field(
        default=None, description="RSA public key path"
    )

    @model_validator(mode="after")
    def validate_test_duration(self):
        """Ensure only one of time, bytes, or blockcount is specified."""
        duration_fields = ["time", "bytes", "blockcount"]
        values = [
            getattr(self, f) for f in duration_fields if getattr(self, f) is not None
        ]
        if len(values) > 1:
            raise ValueError(f"Only one of {duration_fields} can be specified")
        return self

    @model_validator(mode="after")
    def validate_protocol_specific(self):
        """Validate protocol-specific options."""
        protocol = self.protocol

        if protocol == Protocol.UDP:
            if self.no_delay:
                raise ValueError("no_delay is not applicable for UDP")
            if self.congestion_algorithm:
                raise ValueError("congestion_algorithm is not applicable for UDP")

        if protocol == Protocol.SCTP:
            if not self.sctp_streams:
                self.sctp_streams = 1  # Default for SCTP

        return self


class EnvironmentConfig(BaseSettings):
    """Environment configuration using Pydantic Settings for automatic loading."""

    model_config = SettingsConfigDict(
        env_prefix="PIPERF3_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        validate_default=True,
        extra="ignore",
    )

    # Metadata
    name: str = Field(
        default="iperf3_test_environment", description="Environment name/identifier"
    )
    description: Optional[str] = Field(
        default=None, description="Environment description"
    )
    version: str = Field(default="1.0", description="Configuration version")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    created_by: Optional[str] = Field(
        default_factory=lambda: os.environ.get("USER", "unknown"),
        description="Creator information",
    )
    tags: List[str] = Field(default_factory=list, description="Environment tags")

    # Test configuration - these will be populated from environment variables
    # with PIPERF3_ prefix automatically
    server_host: Optional[str] = Field(
        default=None, description="Server hostname or IP address"
    )
    port: int = Field(default=5201, ge=1, le=65535, description="Server port")
    time: Optional[int] = Field(default=10, ge=1, description="Test duration (seconds)")
    bitrate: Optional[str] = Field(default=None, description="Target bitrate")
    parallel_streams: int = Field(
        default=1, ge=1, description="Number of parallel streams"
    )
    protocol: Protocol = Field(default=Protocol.TCP, description="Transport protocol")
    format: Optional[Format] = Field(default=None, description="Output format")
    json_output: bool = Field(default=True, description="Output in JSON format")
    verbose: bool = Field(default=False, description="Verbose output")
    reverse: bool = Field(default=False, description="Reverse test direction")
    bidir: bool = Field(default=False, description="Bidirectional test")

    # Output settings
    output_directory: Optional[Path] = Field(
        default=None, description="Output directory for results"
    )
    run_id: Optional[str] = Field(default=None, description="Run identifier")

    # System information - automatically populated
    node_info: Dict[str, Any] = Field(
        default_factory=dict, description="Node information"
    )
    slurm_info: Dict[str, Any] = Field(
        default_factory=dict, description="SLURM job information"
    )

    def __init__(self, **data):
        """Initialize with automatic system info collection."""
        super().__init__(**data)
        self._collect_system_info()

    def _collect_system_info(self):
        """Automatically collect system and SLURM information."""
        # Node information
        node_info = {
            "hostname": socket.gethostname(),
            "fqdn": socket.getfqdn(),
        }

        # Try to get CPU information
        try:
            with open("/proc/cpuinfo", "r") as f:
                cpuinfo = f.read()
                for line in cpuinfo.split("\n"):
                    if line.startswith("model name"):
                        node_info["cpu_model"] = line.split(":", 1)[1].strip()
                        break
                cpu_count = cpuinfo.count("processor")
                node_info["cpu_count"] = str(cpu_count)
        except Exception:
            pass

        # Try to get memory information
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = f.read()
                for line in meminfo.split("\n"):
                    if line.startswith("MemTotal"):
                        mem_kb = int(line.split()[1])
                        node_info["memory_gb"] = str(round(mem_kb / 1024 / 1024, 2))
                        break
        except Exception:
            pass

        # Update node_info
        self.node_info.update(node_info)

        # SLURM information
        slurm_vars = [
            "SLURM_JOB_ID",
            "SLURM_JOB_NAME",
            "SLURM_JOB_PARTITION",
            "SLURM_JOB_ACCOUNT",
            "SLURM_JOB_NUM_NODES",
            "SLURM_NTASKS",
            "SLURM_CPUS_PER_TASK",
            "SLURM_MEM_PER_NODE",
            "SLURM_NODELIST",
            "SLURM_PROCID",
            "SLURM_LOCALID",
        ]

        slurm_info = {}
        for var in slurm_vars:
            if var in os.environ:
                slurm_info[var.lower()] = os.environ[var]

        if slurm_info:
            self.slurm_info.update(slurm_info)

    def to_client_config(self) -> Optional[IperfClientConfig]:
        """Convert to IperfClientConfig if server_host is provided."""
        if not self.server_host:
            return None

        return IperfClientConfig(
            server_host=self.server_host,
            port=self.port,
            time=self.time,
            bitrate=self.bitrate,
            parallel_streams=self.parallel_streams,
            protocol=self.protocol,
            format=self.format,
            json_output=self.json_output,
            verbose=self.verbose,
            reverse=self.reverse,
            bidir=self.bidir,
        )

    def to_server_config(self) -> IperfServerConfig:
        """Convert to IperfServerConfig."""
        return IperfServerConfig(
            port=self.port,
            format=self.format,
            json_output=self.json_output,
            verbose=self.verbose,
        )

    def get_provenance(self) -> Dict[str, Any]:
        """Get provenance information for this environment."""
        return {
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "tags": self.tags,
            "node_info": self.node_info,
            "slurm_info": self.slurm_info,
        }


class IperfResult(BaseModel):
    """Iperf3 test result with metadata."""

    # Test metadata
    environment_name: str
    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None

    # Test configuration used
    config_used: Union[IperfClientConfig, IperfServerConfig]

    # Raw outputs
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0

    # Parsed JSON results (if available)
    json_results: Optional[Dict[str, Any]] = None

    # File paths
    output_directory: Path
    stdout_file: Optional[Path] = None
    stderr_file: Optional[Path] = None
    json_file: Optional[Path] = None

    # Provenance
    provenance: Dict[str, Any] = Field(default_factory=dict)

    def save_to_directory(self, directory: Path) -> None:
        """Save all result files to the specified directory."""
        directory.mkdir(parents=True, exist_ok=True)

        # Save stdout
        if self.stdout:
            stdout_file = directory / "stdout.txt"
            stdout_file.write_text(self.stdout)
            self.stdout_file = stdout_file

        # Save stderr
        if self.stderr:
            stderr_file = directory / "stderr.txt"
            stderr_file.write_text(self.stderr)
            self.stderr_file = stderr_file

        # Save JSON results
        if self.json_results:
            json_file = directory / "results.json"
            with open(json_file, "w") as f:
                json.dump(self.json_results, f, indent=2)
            self.json_file = json_file

        # Save result metadata
        metadata_file = directory / "result_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(
                self.model_dump(exclude={"stdout", "stderr", "json_results"}),
                f,
                indent=2,
                default=str,
            )

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat(),
            Path: str,
        }
    }

"""Iperf3 command runner and result processor."""

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .models import (
    EnvironmentConfig,
    IperfClientConfig,
    IperfServerConfig,
    IperfResult,
    IperfMode,
    Protocol,
)


class Iperf3Runner:
    """Main class for running iperf3 commands and processing results."""

    def __init__(self, iperf3_path: str = "iperf3"):
        """Initialize the runner with the path to iperf3 executable."""
        self.iperf3_path = iperf3_path
        self._validate_iperf3_availability()

    def _validate_iperf3_availability(self) -> None:
        """Validate that iperf3 is available and get version info."""
        try:
            result = subprocess.run(
                [self.iperf3_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"iperf3 is not working: {result.stderr}")
        except FileNotFoundError:
            raise RuntimeError(f"iperf3 not found at: {self.iperf3_path}")
        except subprocess.TimeoutExpired:
            raise RuntimeError("iperf3 version check timed out")

    def build_command(
        self, config: Union[IperfClientConfig, IperfServerConfig]
    ) -> List[str]:
        """Build the iperf3 command from configuration."""
        cmd = [self.iperf3_path]

        # Determine mode
        if isinstance(config, IperfServerConfig) or config.mode == IperfMode.SERVER:
            cmd.extend(self._build_server_command(config))  # type: ignore
        elif isinstance(config, IperfClientConfig) or config.mode == IperfMode.CLIENT:
            cmd.extend(self._build_client_command(config))  # type: ignore
        else:
            raise ValueError(f"Unknown configuration type: {type(config)}")

        return cmd

    def _build_server_command(self, config: IperfServerConfig) -> List[str]:
        """Build server-specific command arguments."""
        args = ["--server"]

        # Basic server options
        if config.port != 5201:
            args.extend(["--port", str(config.port)])

        if config.bind_address:
            args.extend(["--bind", config.bind_address])

        if config.bind_device:
            args.extend(["--bind-dev", config.bind_device])

        # Server-specific options
        if config.daemon:
            args.append("--daemon")

        if config.one_off:
            args.append("--one-off")

        if config.idle_timeout is not None:
            args.extend(["--idle-timeout", str(config.idle_timeout)])

        if config.server_bitrate_limit:
            args.extend(["--server-bitrate-limit", config.server_bitrate_limit])

        # Authentication
        if config.rsa_private_key_path:
            args.extend(["--rsa-private-key-path", str(config.rsa_private_key_path)])

        if config.authorized_users_path:
            args.extend(["--authorized-users-path", str(config.authorized_users_path)])

        if config.time_skew_threshold is not None:
            args.extend(["--time-skew-threshold", str(config.time_skew_threshold)])

        # Add common options
        args.extend(self._build_common_options(config))

        return args

    def _build_client_command(self, config: IperfClientConfig) -> List[str]:
        """Build client-specific command arguments."""
        args = ["--client", config.server_host]

        if config.port != 5201:
            args.extend(["--port", str(config.port)])

        # Test duration
        if config.time is not None:
            args.extend(["--time", str(config.time)])
        elif config.bytes:
            args.extend(["--bytes", config.bytes])
        elif config.blockcount:
            args.extend(["--blockcount", config.blockcount])

        # Protocol
        if config.protocol == Protocol.UDP:
            args.append("--udp")
        elif config.protocol == Protocol.SCTP:
            args.append("--sctp")

        # Bitrate and pacing
        if config.bitrate:
            args.extend(["--bitrate", config.bitrate])

        if config.pacing_timer != 1000:
            args.extend(["--pacing-timer", str(config.pacing_timer)])

        if config.fq_rate:
            args.extend(["--fq-rate", config.fq_rate])

        # Connection settings
        if config.connect_timeout is not None:
            args.extend(["--connect-timeout", str(config.connect_timeout)])

        if config.parallel_streams > 1:
            args.extend(["--parallel", str(config.parallel_streams)])

        if config.reverse:
            args.append("--reverse")

        if config.bidir:
            args.append("--bidir")

        # Buffer and packet settings
        if config.length:
            args.extend(["--length", config.length])

        if config.window:
            args.extend(["--window", config.window])

        if config.set_mss is not None:
            args.extend(["--set-mss", str(config.set_mss)])

        if config.no_delay:
            args.append("--no-delay")

        # Advanced options
        if config.client_port is not None:
            args.extend(["--cport", str(config.client_port)])

        if config.tos is not None:
            args.extend(["--tos", str(config.tos)])

        if config.dscp is not None:
            args.extend(["--dscp", str(config.dscp)])

        if config.flowlabel is not None:
            args.extend(["--flowlabel", str(config.flowlabel)])

        # File operations
        if config.file_input:
            args.extend(["--file", str(config.file_input)])

        # SCTP-specific
        if config.sctp_streams is not None:
            args.extend(["--nstreams", str(config.sctp_streams)])

        if config.xbind:
            for bind_addr in config.xbind:
                args.extend(["--xbind", bind_addr])

        # Performance options
        if config.zerocopy:
            args.append("--zerocopy")

        if config.skip_rx_copy:
            args.append("--skip-rx-copy")

        if config.omit is not None:
            args.extend(["--omit", str(config.omit)])

        # Output customization
        if config.title:
            args.extend(["--title", config.title])

        if config.extra_data:
            args.extend(["--extra-data", config.extra_data])

        # Advanced features
        if config.congestion_algorithm:
            args.extend(["--congestion", config.congestion_algorithm.value])

        if config.get_server_output:
            args.append("--get-server-output")

        if config.udp_counters_64bit:
            args.append("--udp-counters-64bit")

        if config.repeating_payload:
            args.append("--repeating-payload")

        if config.dont_fragment:
            args.append("--dont-fragment")

        # Authentication
        if config.username:
            args.extend(["--username", config.username])

        if config.rsa_public_key_path:
            args.extend(["--rsa-public-key-path", str(config.rsa_public_key_path)])

        # Add common options
        args.extend(self._build_common_options(config))

        return args

    def _build_common_options(
        self, config: Union[IperfClientConfig, IperfServerConfig]
    ) -> List[str]:
        """Build common options for both client and server."""
        args = []

        # Output format
        if config.format:
            args.extend(["--format", config.format.value])

        if config.interval != 1.0:
            args.extend(["--interval", str(config.interval)])

        if config.json_output:
            args.append("--json")

        if config.json_stream:
            args.append("--json-stream")

        if config.verbose:
            args.append("--verbose")

        # Advanced settings
        if config.cpu_affinity:
            args.extend(["--affinity", str(config.cpu_affinity)])

        if config.pidfile:
            args.extend(["--pidfile", str(config.pidfile)])

        if config.logfile:
            args.extend(["--logfile", str(config.logfile)])

        if config.force_flush:
            args.append("--forceflush")

        if config.timestamps:
            if config.timestamps == "default":
                args.append("--timestamps")
            else:
                args.append(f"--timestamps={config.timestamps}")

        if config.debug:
            args.append("--debug")

        # IP version
        if config.ipv4_only:
            args.append("--version4")
        elif config.ipv6_only:
            args.append("--version6")

        # Timeouts
        if config.rcv_timeout != 120000:
            args.extend(["--rcv-timeout", str(config.rcv_timeout)])

        if config.snd_timeout is not None:
            args.extend(["--snd-timeout", str(config.snd_timeout)])

        # Security
        if config.use_pkcs1_padding:
            args.append("--use-pkcs1-padding")

        # MPTCP
        if config.mptcp:
            args.append("--mptcp")

        return args

    def run(
        self,
        config: Union[IperfClientConfig, IperfServerConfig],
        env_config: EnvironmentConfig,
        timeout: Optional[int] = None,
    ) -> IperfResult:
        """Run iperf3 with the given configuration and return results."""

        # Generate run ID if not provided
        run_id = env_config.run_id or str(uuid.uuid4())

        # Create output directory
        output_dir = self._create_output_directory(env_config, run_id)

        # Build command
        cmd = self.build_command(config)

        # Save command for reference
        cmd_file = output_dir / "command.txt"
        cmd_file.write_text(" ".join(cmd))

        # Initialize result
        result = IperfResult(
            environment_name=env_config.name,
            run_id=run_id,
            start_time=datetime.now(timezone.utc),
            config_used=config,
            output_directory=output_dir,
            provenance=env_config.get_provenance(),
        )

        try:
            # Run the command
            process_result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=output_dir,
                env={**os.environ, **env_config.env_vars},
            )

            result.stdout = process_result.stdout
            result.stderr = process_result.stderr
            result.return_code = process_result.returncode
            result.end_time = datetime.now(timezone.utc)

            # Try to parse JSON output
            if config.json_output and result.stdout:
                try:
                    result.json_results = json.loads(result.stdout)
                except json.JSONDecodeError:
                    # If stdout is not valid JSON, try to extract JSON from it
                    lines = result.stdout.split("\n")
                    for line in lines:
                        if line.strip().startswith("{"):
                            try:
                                result.json_results = json.loads(line)
                                break
                            except json.JSONDecodeError:
                                continue

        except subprocess.TimeoutExpired:
            result.stderr = f"Command timed out after {timeout} seconds"
            result.return_code = -1
            result.end_time = datetime.now(timezone.utc)
        except Exception as e:
            result.stderr = f"Unexpected error: {str(e)}"
            result.return_code = -1
            result.end_time = datetime.now(timezone.utc)

        # Save results to files
        result.save_to_directory(output_dir)

        return result

    def _create_output_directory(
        self, env_config: EnvironmentConfig, run_id: str
    ) -> Path:
        """Create and return the output directory for this run."""
        base_dir = env_config.output_directory or Path("./results")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Create a unique directory name
        dir_name = f"{env_config.name}_{run_id[:8]}_{timestamp}"
        output_dir = base_dir / dir_name
        output_dir.mkdir(parents=True, exist_ok=True)

        return output_dir

    def run_server_background(
        self, config: IperfServerConfig, env_config: EnvironmentConfig
    ) -> Tuple[subprocess.Popen, Path]:
        """Start an iperf3 server in the background and return the process and output directory."""

        # Generate run ID
        run_id = env_config.run_id or str(uuid.uuid4())

        # Create output directory
        output_dir = self._create_output_directory(env_config, run_id)

        # Build command
        cmd = self.build_command(config)

        # Save command for reference
        cmd_file = output_dir / "command.txt"
        cmd_file.write_text(" ".join(cmd))

        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=output_dir,
            env={**os.environ, **env_config.env_vars},
        )

        return process, output_dir

    def get_version(self) -> str:
        """Get iperf3 version information."""
        try:
            result = subprocess.run(
                [self.iperf3_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error getting version: {str(e)}"

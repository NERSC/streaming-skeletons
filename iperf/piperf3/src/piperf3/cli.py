"""Command-line interface for piperf3 using Typer."""

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .config import load_environment_config
from .runner import Iperf3Runner
from .plotting import IperfPlotter

app = typer.Typer(
    name="piperf3",
    help="A fully-featured Python wrapper for iperf3 with configuration management and plotting.",
    add_completion=False,
)

console = Console()


@app.command()
def client(
    server: str = typer.Argument(..., help="Server hostname or IP address"),
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Configuration file (YAML or TOML)"
    ),
    env_file: Optional[Path] = typer.Option(
        None, "--env-file", "-e", help="Environment file (.env)"
    ),
    port: Optional[int] = typer.Option(
        None, "--port", "-p", help="Server port (overrides config)"
    ),
    duration: Optional[int] = typer.Option(
        None, "--time", "-t", help="Test duration in seconds (overrides config)"
    ),
    bitrate: Optional[str] = typer.Option(
        None,
        "--bitrate",
        "-b",
        help="Target bitrate (e.g., '10M', '1G') (overrides config)",
    ),
    parallel: Optional[int] = typer.Option(
        None, "--parallel", "-P", help="Number of parallel streams (overrides config)"
    ),
    protocol: Optional[str] = typer.Option(
        None, "--protocol", help="Protocol: tcp, udp, or sctp (overrides config)"
    ),
    reverse: bool = typer.Option(
        False, "--reverse", "-R", help="Reverse test direction (server sends to client)"
    ),
    bidir: bool = typer.Option(False, "--bidir", help="Bidirectional test"),
    json_output: bool = typer.Option(
        False, "--json", "-J", help="Output results in JSON format"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output directory for results"
    ),
    plot: bool = typer.Option(
        True, "--plot/--no-plot", help="Generate plots from results"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run iperf3 client with the specified configuration."""

    # Load base configuration from environment/files
    try:
        env_config = load_environment_config(
            config_file=config_file,
            env_file=env_file,
            # Override with CLI arguments
            server_host=server,
            port=port if port is not None else None,
            time=duration if duration is not None else None,
            bitrate=bitrate,
            parallel_streams=parallel if parallel is not None else None,
            protocol=protocol,
            reverse=reverse,
            bidir=bidir,
            json_output=json_output,
            output_directory=output_dir,
            verbose=verbose,
        )
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Ensure we have a server host
    if not env_config.server_host:
        console.print("[red]Server host is required but not specified[/red]")
        raise typer.Exit(1)

    # Force JSON output if plotting is requested
    if plot and not env_config.json_output:
        console.print("[yellow]Enabling JSON output for plotting[/yellow]")
        env_config = env_config.model_copy(update={"json_output": True})

    # Convert to client config
    client_config = env_config.to_client_config()
    if not client_config:
        console.print("[red]Could not create client configuration[/red]")
        raise typer.Exit(1)

    # Display configuration
    config_info = (
        f"Server: {client_config.server_host}:{client_config.port}\n"
        f"Duration: {client_config.time or 10}s\n"
        f"Protocol: {client_config.protocol or 'tcp'}\n"
        f"Parallel streams: {client_config.parallel_streams or 1}"
    )

    console.print(
        Panel(
            config_info,
            title="[bold blue]Client Configuration[/bold blue]",
            expand=False,
        )
    )

    # Initialize runner
    runner = Iperf3Runner()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running iperf3 client test...", total=None)
        try:
            result = runner.run(client_config, env_config)
            progress.update(task, description="✅ Test completed")
        except Exception as e:
            progress.update(task, description=f"❌ Test failed: {e}")
            console.print(f"[red]Error running test: {e}[/red]")
            raise typer.Exit(1)

    # Display results
    _display_results(result, verbose)

    # Generate plots if requested
    if plot and result.json_results:
        _generate_plots(result, console)

    console.print(f"[green]Results saved to: {result.output_directory}[/green]")


@app.command()
def server(
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Configuration file (YAML or TOML)"
    ),
    env_file: Optional[Path] = typer.Option(
        None, "--env-file", "-e", help="Environment file (.env)"
    ),
    port: Optional[int] = typer.Option(
        None, "--port", "-p", help="Server port (overrides config)"
    ),
    bind_address: Optional[str] = typer.Option(
        None, "--bind", "-B", help="Bind to specific address (overrides config)"
    ),
    daemon: bool = typer.Option(False, "--daemon", "-D", help="Run as daemon"),
    one_off: bool = typer.Option(
        False, "--one-off", "-1", help="Handle one client then exit"
    ),
    json_output: bool = typer.Option(
        False, "--json", "-J", help="Output results in JSON format"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output-dir", "-o", help="Output directory for results"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Run iperf3 server with the specified configuration."""

    # Load base configuration
    try:
        env_config = load_environment_config(
            config_file=config_file,
            env_file=env_file,
            # Override with CLI arguments
            port=port if port is not None else None,
            json_output=json_output,
            verbose=verbose,
            output_directory=output_dir,
        )
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    # Convert to server config
    server_config = env_config.to_server_config()

    # Apply additional CLI overrides that aren't in the base config
    server_updates = {}
    if bind_address is not None:
        server_updates["bind_address"] = bind_address
    if daemon:
        server_updates["daemon"] = daemon
    if one_off:
        server_updates["one_off"] = one_off

    if server_updates:
        server_config = server_config.model_copy(update=server_updates)

    # Initialize runner
    runner = Iperf3Runner()

    if daemon:
        console.print(
            Panel(
                f"[bold green]Starting iperf3 server in daemon mode[/bold green]\n"
                f"Port: {server_config.port or 5201}\n"
                f"Bind: {server_config.bind_address or 'all interfaces'}",
                title="Server Configuration",
            )
        )

        try:
            process, output_dir = runner.run_server_background(
                server_config, env_config
            )
            console.print(f"[green]Server started with PID {process.pid}[/green]")
            console.print(f"[green]Output directory: {output_dir}[/green]")

            # Save PID file if output directory is available
            if output_dir:
                pid_file = output_dir / "server.pid"
                pid_file.write_text(str(process.pid))

        except Exception as e:
            console.print(f"[red]Error starting server: {e}[/red]")
            raise typer.Exit(1)

    else:
        console.print(
            Panel(
                f"[bold green]Starting iperf3 server[/bold green]\n"
                f"Port: {server_config.port or 5201}\n"
                f"Bind: {server_config.bind_address or 'all interfaces'}\n"
                f"One-off: {server_config.one_off}",
                title="Server Configuration",
            )
        )

        try:
            result = runner.run(server_config, env_config)
            _display_results(result, verbose)
            console.print(f"[green]Results saved to: {result.output_directory}[/green]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Server interrupted by user[/yellow]")
        except Exception as e:
            console.print(f"[red]Error running server: {e}[/red]")
            raise typer.Exit(1)


@app.command()
def plot_results(
    result_dirs: List[Path] = typer.Argument(
        ..., help="Result directories containing iperf3 JSON outputs"
    ),
    output_dir: Path = typer.Option(
        Path("./plots"), "--output-dir", "-o", help="Directory to save plots"
    ),
    title: str = typer.Option(
        "Iperf3 Results Analysis", "--title", "-t", help="Title for comparison plots"
    ),
    format: str = typer.Option(
        "png", "--format", "-f", help="Output format (png, pdf, svg)"
    ),
):
    """Generate plots from existing iperf3 result directories."""

    from .models import IperfResult

    results = []

    # Load results from directories
    for result_dir in result_dirs:
        if not result_dir.exists():
            console.print(f"[red]Result directory not found: {result_dir}[/red]")
            continue

        json_file = result_dir / "results.json"
        if not json_file.exists():
            console.print(f"[yellow]No results.json found in {result_dir}[/yellow]")
            continue

        try:
            import json
            from datetime import datetime, timezone

            with open(json_file) as f:
                json_data = json.load(f)

            # Create a minimal IperfResult for plotting
            # Use dummy values for required fields since we're only plotting
            from .models import IperfClientConfig

            dummy_config = IperfClientConfig(server_host="unknown")

            result = IperfResult(
                environment_name=result_dir.name,
                run_id=result_dir.name.split("_")[-1]
                if "_" in result_dir.name
                else "unknown",
                start_time=datetime.now(timezone.utc),
                config_used=dummy_config,
                output_directory=result_dir,
                json_results=json_data,
            )
            results.append(result)

        except Exception as e:
            console.print(f"[red]Error loading {json_file}: {e}[/red]")

    if not results:
        console.print("[red]No valid results found[/red]")
        raise typer.Exit(1)

    # Generate plots
    plotter = IperfPlotter()

    try:
        created_files = plotter.create_dashboard(results, output_dir, title)

        console.print(f"[green]Created {len(created_files)} plot files:[/green]")
        for file_path in created_files:
            console.print(f"  • {file_path}")

    except Exception as e:
        console.print(f"[red]Error creating plots: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def create_config(
    output_dir: Path = typer.Option(
        Path("."),
        "--output-dir",
        "-o",
        help="Directory to create example configuration files",
    ),
    config_type: str = typer.Option(
        "all", "--type", "-t", help="Type of config to create: client, server, or all"
    ),
):
    """Create example configuration files."""

    from .config import create_example_configs

    configs = create_example_configs()
    output_dir.mkdir(parents=True, exist_ok=True)

    created_files = []

    if config_type in ["client", "all"]:
        client_file = output_dir / "client_example.yaml"
        import yaml

        with open(client_file, "w") as f:
            yaml.dump(configs["client.yaml"], f, default_flow_style=False, indent=2)
        created_files.append(client_file)

    if config_type in ["server", "all"]:
        server_file = output_dir / "server_example.yaml"
        import yaml

        with open(server_file, "w") as f:
            yaml.dump(configs["server.yaml"], f, default_flow_style=False, indent=2)
        created_files.append(server_file)

    if config_type in ["all"]:
        env_file = output_dir / "example.env"
        env_file.write_text(configs["example.env"])
        created_files.append(env_file)

    console.print(
        f"[green]Created {len(created_files)} example configuration files:[/green]"
    )
    for file_path in created_files:
        console.print(f"  • {file_path}")


@app.command()
def version():
    """Show version information."""
    runner = Iperf3Runner()
    iperf3_version = runner.get_version()

    console.print(
        Panel(
            f"[bold blue]piperf3[/bold blue] - Python wrapper for iperf3\n"
            f"Version: 0.1.0\n\n"
            f"[bold]iperf3 Information:[/bold]\n{iperf3_version}",
            title="Version Information",
        )
    )


def _display_results(result, verbose: bool = False):
    """Display test results in a nice format."""

    if result.return_code != 0:
        console.print(f"[red]Test failed with return code {result.return_code}[/red]")
        if result.stderr:
            console.print(f"[red]Error: {result.stderr}[/red]")
        return

    # Create results table
    table = Table(title="Test Results Summary")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Environment", result.environment_name)
    table.add_row("Run ID", result.run_id[:8])
    table.add_row("Start Time", str(result.start_time))
    table.add_row(
        "Duration",
        str(result.end_time - result.start_time) if result.end_time else "N/A",
    )
    table.add_row("Return Code", str(result.return_code))

    if result.json_results:
        end_data = result.json_results.get("end", {})
        sum_sent = end_data.get("sum_sent", {})
        sum_received = end_data.get("sum_received", {})

        if sum_sent:
            table.add_row(
                "Sent Throughput",
                f"{sum_sent.get('bits_per_second', 0) / 1e9:.2f} Gbps",
            )
            table.add_row("Sent Data", f"{sum_sent.get('bytes', 0) / 1e6:.2f} MB")

        if sum_received:
            table.add_row(
                "Received Throughput",
                f"{sum_received.get('bits_per_second', 0) / 1e9:.2f} Gbps",
            )
            table.add_row(
                "Received Data", f"{sum_received.get('bytes', 0) / 1e6:.2f} MB"
            )

    console.print(table)

    if verbose and result.stdout:
        console.print("\n[bold]Raw Output:[/bold]")
        console.print(Panel(result.stdout, title="stdout", border_style="blue"))

    if result.stderr:
        console.print("\n[bold]Errors/Warnings:[/bold]")
        console.print(Panel(result.stderr, title="stderr", border_style="red"))


def _generate_plots(result, console):
    """Generate plots for a single result."""
    plotter = IperfPlotter()

    try:
        plot_dir = result.output_directory / "plots"
        plot_dir.mkdir(exist_ok=True)

        # Time series plot
        fig1 = plotter.plot_throughput_time_series(result)
        plot_file1 = plot_dir / "throughput_timeseries.png"
        fig1.savefig(plot_file1, dpi=300, bbox_inches="tight")

        # Multi-stream plot if applicable
        try:
            fig2 = plotter.plot_multi_stream_comparison(result)
            plot_file2 = plot_dir / "stream_comparison.png"
            fig2.savefig(plot_file2, dpi=300, bbox_inches="tight")
        except ValueError:
            pass

        console.print(f"[green]Plots saved to: {plot_dir}[/green]")

    except Exception as e:
        console.print(f"[yellow]Warning: Could not generate plots: {e}[/yellow]")


if __name__ == "__main__":
    app()

"""Plotting utilities for iperf3 results visualization."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np

from .models import IperfResult


class IperfPlotter:
    """Class for creating plots from iperf3 results."""

    def __init__(self, style: str = "darkgrid"):
        """Initialize the plotter with a seaborn style."""
        sns.set_style(style)
        plt.style.use("seaborn-v0_8-darkgrid")
        self.colors = sns.color_palette("husl", 10)

    def plot_throughput_time_series(
        self,
        result: IperfResult,
        output_file: Optional[Path] = None,
        title: Optional[str] = None,
    ) -> plt.Figure:
        """Plot throughput over time from iperf3 results."""

        if not result.json_results:
            raise ValueError("JSON results required for plotting")

        # Extract time series data
        intervals = result.json_results.get("intervals", [])
        if not intervals:
            raise ValueError("No interval data found in results")

        # Prepare data
        times = []
        throughput_bits = []
        throughput_bytes = []
        retransmits = []

        for interval in intervals:
            streams = interval.get("streams", [])
            if streams:
                # Sum across all streams for this interval
                sum_data = interval.get("sum", {})
                times.append(sum_data.get("start", 0))
                throughput_bits.append(
                    sum_data.get("bits_per_second", 0) / 1e9
                )  # Convert to Gbps
                throughput_bytes.append(sum_data.get("bytes", 0) / 1e6)  # Convert to MB
                retransmits.append(sum_data.get("retransmits", 0))

        # Create the plot
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

        # Plot 1: Throughput over time
        ax1.plot(times, throughput_bits, marker="o", color=self.colors[0], linewidth=2)
        ax1.set_xlabel("Time (seconds)")
        ax1.set_ylabel("Throughput (Gbps)")
        ax1.set_title("Throughput vs Time")
        ax1.grid(True, alpha=0.3)

        # Plot 2: Cumulative data transferred
        cumulative_bytes = np.cumsum(throughput_bytes)
        ax2.plot(times, cumulative_bytes, marker="s", color=self.colors[1], linewidth=2)
        ax2.set_xlabel("Time (seconds)")
        ax2.set_ylabel("Cumulative Data (MB)")
        ax2.set_title("Cumulative Data Transfer")
        ax2.grid(True, alpha=0.3)

        # Plot 3: Retransmissions (if TCP)
        if any(r > 0 for r in retransmits):
            ax3.bar(times, retransmits, color=self.colors[2], alpha=0.7)
            ax3.set_xlabel("Time (seconds)")
            ax3.set_ylabel("Retransmissions")
            ax3.set_title("Retransmissions per Interval")
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(
                0.5,
                0.5,
                "No Retransmissions",
                ha="center",
                va="center",
                transform=ax3.transAxes,
                fontsize=12,
            )
            ax3.set_title("Retransmissions per Interval")

        # Plot 4: Statistics summary
        stats = self._extract_summary_stats(result.json_results)
        stats_text = []
        for key, value in stats.items():
            stats_text.append(f"{key}: {value}")

        ax4.text(
            0.1,
            0.9,
            "\n".join(stats_text),
            transform=ax4.transAxes,
            fontsize=10,
            verticalalignment="top",
            fontfamily="monospace",
        )
        ax4.set_title("Test Summary")
        ax4.axis("off")

        # Set overall title
        if title:
            fig.suptitle(title, fontsize=16, fontweight="bold")
        else:
            fig.suptitle(
                f"Iperf3 Results - {result.environment_name}",
                fontsize=16,
                fontweight="bold",
            )

        plt.tight_layout()

        # Save if requested
        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches="tight")

        return fig

    def plot_multi_stream_comparison(
        self, result: IperfResult, output_file: Optional[Path] = None
    ) -> plt.Figure:
        """Plot comparison of multiple parallel streams."""

        if not result.json_results:
            raise ValueError("JSON results required for plotting")

        intervals = result.json_results.get("intervals", [])
        if not intervals:
            raise ValueError("No interval data found in results")

        # Extract per-stream data
        stream_data = {}
        for interval in intervals:
            time = interval.get("sum", {}).get("start", 0)
            streams = interval.get("streams", [])

            for stream in streams:
                stream_id = stream.get("socket", 0)
                if stream_id not in stream_data:
                    stream_data[stream_id] = {"times": [], "throughput": []}

                stream_data[stream_id]["times"].append(time)
                stream_data[stream_id]["throughput"].append(
                    stream.get("bits_per_second", 0) / 1e9
                )

        # Create the plot
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))

        # Plot 1: Individual stream throughput
        for i, (stream_id, data) in enumerate(stream_data.items()):
            color = self.colors[i % len(self.colors)]
            ax1.plot(
                data["times"],
                data["throughput"],
                marker="o",
                color=color,
                label=f"Stream {stream_id}",
                linewidth=2,
            )

        ax1.set_xlabel("Time (seconds)")
        ax1.set_ylabel("Throughput (Gbps)")
        ax1.set_title("Individual Stream Throughput")
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Stream throughput distribution
        all_throughputs = []
        stream_labels = []
        for stream_id, data in stream_data.items():
            all_throughputs.extend(data["throughput"])
            stream_labels.extend([f"Stream {stream_id}"] * len(data["throughput"]))

        df = pd.DataFrame(
            {"Throughput (Gbps)": all_throughputs, "Stream": stream_labels}
        )
        sns.boxplot(data=df, x="Stream", y="Throughput (Gbps)", ax=ax2)
        ax2.set_title("Throughput Distribution by Stream")
        ax2.tick_params(axis="x", rotation=45)

        plt.tight_layout()

        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches="tight")

        return fig

    def plot_comparison(
        self,
        results: List[IperfResult],
        output_file: Optional[Path] = None,
        title: str = "Iperf3 Results Comparison",
    ) -> plt.Figure:
        """Plot comparison of multiple iperf3 results."""

        if not results:
            raise ValueError("At least one result is required")

        # Prepare comparison data
        comparison_data = []
        for result in results:
            if result.json_results:
                summary = result.json_results.get("end", {})
                sum_sent = summary.get("sum_sent", {})
                sum_received = summary.get("sum_received", {})

                comparison_data.append(
                    {
                        "name": result.environment_name,
                        "run_id": result.run_id[:8],
                        "sent_gbps": sum_sent.get("bits_per_second", 0) / 1e9,
                        "received_gbps": sum_received.get("bits_per_second", 0) / 1e9,
                        "sent_mb": sum_sent.get("bytes", 0) / 1e6,
                        "received_mb": sum_received.get("bytes", 0) / 1e6,
                        "retransmits": sum_sent.get("retransmits", 0),
                        "duration": sum_sent.get("seconds", 0),
                    }
                )

        if not comparison_data:
            raise ValueError("No valid JSON results found for comparison")

        df = pd.DataFrame(comparison_data)

        # Create comparison plots
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))

        # Plot 1: Throughput comparison
        x_pos = np.arange(len(df))
        width = 0.35

        ax1.bar(
            x_pos - width / 2,
            df["sent_gbps"],
            width,
            label="Sent",
            color=self.colors[0],
        )
        ax1.bar(
            x_pos + width / 2,
            df["received_gbps"],
            width,
            label="Received",
            color=self.colors[1],
        )

        ax1.set_xlabel("Test Runs")
        ax1.set_ylabel("Throughput (Gbps)")
        ax1.set_title("Throughput Comparison")
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(
            [f"{row['name']}\n{row['run_id']}" for _, row in df.iterrows()],
            rotation=45,
            ha="right",
        )
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # Plot 2: Data transfer comparison
        ax2.bar(
            x_pos - width / 2, df["sent_mb"], width, label="Sent", color=self.colors[2]
        )
        ax2.bar(
            x_pos + width / 2,
            df["received_mb"],
            width,
            label="Received",
            color=self.colors[3],
        )

        ax2.set_xlabel("Test Runs")
        ax2.set_ylabel("Data Transferred (MB)")
        ax2.set_title("Data Transfer Comparison")
        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(
            [f"{row['name']}\n{row['run_id']}" for _, row in df.iterrows()],
            rotation=45,
            ha="right",
        )
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Plot 3: Retransmissions
        if df["retransmits"].sum() > 0:
            ax3.bar(x_pos, df["retransmits"], color=self.colors[4])
            ax3.set_xlabel("Test Runs")
            ax3.set_ylabel("Retransmissions")
            ax3.set_title("Retransmissions Comparison")
            ax3.set_xticks(x_pos)
            ax3.set_xticklabels(
                [f"{row['name']}\n{row['run_id']}" for _, row in df.iterrows()],
                rotation=45,
                ha="right",
            )
            ax3.grid(True, alpha=0.3)
        else:
            ax3.text(
                0.5,
                0.5,
                "No Retransmissions",
                ha="center",
                va="center",
                transform=ax3.transAxes,
                fontsize=12,
            )
            ax3.set_title("Retransmissions Comparison")

        # Plot 4: Duration comparison
        ax4.bar(x_pos, df["duration"], color=self.colors[5])
        ax4.set_xlabel("Test Runs")
        ax4.set_ylabel("Duration (seconds)")
        ax4.set_title("Test Duration Comparison")
        ax4.set_xticks(x_pos)
        ax4.set_xticklabels(
            [f"{row['name']}\n{row['run_id']}" for _, row in df.iterrows()],
            rotation=45,
            ha="right",
        )
        ax4.grid(True, alpha=0.3)

        fig.suptitle(title, fontsize=16, fontweight="bold")
        plt.tight_layout()

        if output_file:
            plt.savefig(output_file, dpi=300, bbox_inches="tight")

        return fig

    def create_dashboard(
        self,
        results: List[IperfResult],
        output_dir: Path,
        title: str = "Iperf3 Performance Dashboard",
    ) -> List[Path]:
        """Create a comprehensive dashboard with multiple plots."""

        output_dir.mkdir(parents=True, exist_ok=True)
        created_files = []

        # Individual result plots
        for i, result in enumerate(results):
            if result.json_results:
                # Time series plot
                fig1 = self.plot_throughput_time_series(
                    result, title=f"{result.environment_name} - {result.run_id[:8]}"
                )
                file1 = output_dir / f"timeseries_{i:02d}_{result.run_id[:8]}.png"
                fig1.savefig(file1, dpi=300, bbox_inches="tight")
                created_files.append(file1)
                plt.close(fig1)

                # Multi-stream plot (if applicable)
                try:
                    fig2 = self.plot_multi_stream_comparison(result)
                    file2 = output_dir / f"streams_{i:02d}_{result.run_id[:8]}.png"
                    fig2.savefig(file2, dpi=300, bbox_inches="tight")
                    created_files.append(file2)
                    plt.close(fig2)
                except ValueError:
                    pass  # Skip if no multi-stream data

        # Comparison plot
        if len(results) > 1:
            fig3 = self.plot_comparison(results, title=title)
            file3 = output_dir / "comparison.png"
            fig3.savefig(file3, dpi=300, bbox_inches="tight")
            created_files.append(file3)
            plt.close(fig3)

        return created_files

    def _extract_summary_stats(self, json_results: Dict[str, Any]) -> Dict[str, str]:
        """Extract summary statistics from JSON results."""
        stats = {}

        end_data = json_results.get("end", {})
        sum_sent = end_data.get("sum_sent", {})
        sum_received = end_data.get("sum_received", {})

        # Basic stats
        stats["Start Time"] = (
            json_results.get("start", {}).get("timestamp", {}).get("time", "N/A")
        )
        stats["Duration"] = f"{sum_sent.get('seconds', 0):.2f} sec"
        stats["Protocol"] = (
            json_results.get("start", {}).get("test_start", {}).get("protocol", "N/A")
        )

        # Throughput
        sent_bps = sum_sent.get("bits_per_second", 0)
        recv_bps = sum_received.get("bits_per_second", 0)
        stats["Sent Throughput"] = f"{sent_bps / 1e9:.2f} Gbps"
        stats["Recv Throughput"] = f"{recv_bps / 1e9:.2f} Gbps"

        # Data transfer
        sent_bytes = sum_sent.get("bytes", 0)
        recv_bytes = sum_received.get("bytes", 0)
        stats["Sent Data"] = f"{sent_bytes / 1e6:.2f} MB"
        stats["Recv Data"] = f"{recv_bytes / 1e6:.2f} MB"

        # TCP-specific
        if sum_sent.get("retransmits") is not None:
            stats["Retransmissions"] = str(sum_sent.get("retransmits", 0))
            stats["Congestion Window"] = f"{sum_sent.get('mean_cwnd', 0):.0f} KB"

        return stats

    @staticmethod
    def save_results_csv(results: List[IperfResult], output_file: Path) -> None:
        """Save results summary to CSV file."""

        csv_data = []
        for result in results:
            row = {
                "environment_name": result.environment_name,
                "run_id": result.run_id,
                "start_time": result.start_time,
                "end_time": result.end_time,
                "return_code": result.return_code,
                "output_directory": str(result.output_directory),
            }

            if result.json_results:
                end_data = result.json_results.get("end", {})
                sum_sent = end_data.get("sum_sent", {})
                sum_received = end_data.get("sum_received", {})

                row.update(
                    {
                        "sent_bits_per_second": sum_sent.get("bits_per_second", 0),
                        "sent_bytes": sum_sent.get("bytes", 0),
                        "sent_seconds": sum_sent.get("seconds", 0),
                        "sent_retransmits": sum_sent.get("retransmits", 0),
                        "received_bits_per_second": sum_received.get(
                            "bits_per_second", 0
                        ),
                        "received_bytes": sum_received.get("bytes", 0),
                        "received_seconds": sum_received.get("seconds", 0),
                    }
                )

            csv_data.append(row)

        df = pd.DataFrame(csv_data)
        df.to_csv(output_file, index=False)

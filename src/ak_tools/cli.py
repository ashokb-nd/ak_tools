"""Command-line interface for ak_tools."""

from __future__ import annotations

from pathlib import Path

import click

from .analytics_log_parser import clean_log_in_folder
from .data_utils import calculate_lane_score, hi


@click.group(help="My personal work toolbox.")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Top-level Click command group."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


@cli.command("process", help="Clean and normalize work data.")
@click.option("--input", "input_path", required=True, type=click.Path(path_type=Path), help="Path to raw data file")
@click.option("--threshold", default=0.5, show_default=True, type=float, help="Sensitivity threshold")
@click.option("--deviation", default=0.24, show_default=True, type=float, help="Deviation value for lane score")
@click.option("--decay", default=0.1, show_default=True, type=float, help="Decay factor (0-1)")
@click.pass_context
def process_cmd(
    ctx: click.Context,
    input_path: Path,
    threshold: float,
    deviation: float,
    decay: float,
) -> None:
    """Process data and compute a simple lane score."""
    try:
        if not 0 <= threshold <= 1:
            raise click.ClickException("threshold must be between 0 and 1")

        lane_score = calculate_lane_score(deviation=deviation, decay=decay)

        if ctx.obj.get("verbose"):
            click.echo(f"Processing {input_path} with threshold={threshold}")

        click.echo(f"lane_score={lane_score:.6f}")
    except click.ClickException:
        raise
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("analyze", help="Run analysis logic on prepared data.")
@click.option("--source", required=True, type=click.Path(path_type=Path), help="Path to prepared data")
def analyze_cmd(source: Path) -> None:
    """Analyze prepared data."""
    try:
        click.echo(f"Done. analyzed={source}")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("report", help="Generate a summary report file.")
@click.option("--output", required=True, type=click.Path(path_type=Path), help="Report output path")
def report_cmd(output: Path) -> None:
    """Generate a report artifact."""
    try:
        click.echo(f"Done. report={output}")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("hi", help="Print a quick greeting for CLI smoke testing.")
def hi_cmd() -> None:
    """Print a simple hi message."""
    try:
        hi()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("clean_log", help="Find analytics.log and save analytics_filtered.log, with optional extra keywords.")
@click.option("--folder", default=".", show_default=True, help="Folder containing analytics.log")
@click.argument("keywords", nargs=-1)
def clean_log_cmd(folder: str, keywords: tuple[str, ...]) -> None:
    """Clean analytics.log in the given folder and allow extra filter keywords."""
    try:
        output_file = clean_log_in_folder(folder=folder, extra_keywords=keywords)
        click.echo(f"Filtered log saved to: {output_file}")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def process_data_entry() -> None:
    """Backward-compatible single command alias for existing users."""
    from sys import argv

    cli.main(args=["process", *argv[1:]], prog_name="process-data", standalone_mode=True)


def main() -> None:
    """Primary package entrypoint for the `ak-tools` command."""
    cli(obj={})

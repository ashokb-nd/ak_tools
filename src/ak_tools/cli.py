"""
Read the following:

click - group, command, option, argument, echo, ClickException
- click nested groups and commands 
"""

from __future__ import annotations

import click

from .analytics_log_parser import clean_log_in_folder
from .data_utils import hi


@click.group(help="My personal work toolbox.")
def cli() -> None:
    """Top-level Click command group."""
    return None

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


def main() -> None:
    """Primary package entrypoint for the `ak-tools` command."""
    cli()

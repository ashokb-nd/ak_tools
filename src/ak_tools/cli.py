"""
Read the following:

click - group, command, option, argument, echo, ClickException
- click nested groups and commands 
"""

from __future__ import annotations

import configparser
from pathlib import Path

import click

from .analytics_log_parser import clean_log_in_folder
from .model_fetcher import fetch_all_models


DEFAULT_FETCH_CONFIG_PATH = "/data4/ashok/REPROCESSING/analytics/src/nd_config_bagheera2_NA_US.ini"
DEFAULT_FETCH_LOCAL_PATH = "/data4/ashok/REPROCESSING/autocam"
USER_CONFIG_PATH = Path.home() / ".ak_tools" / "config.ini"
FETCH_SECTION = "fetch_all_models"


def _read_user_config() -> configparser.ConfigParser:
    """Read user-level ak_tools config if present."""
    config = configparser.ConfigParser()
    if USER_CONFIG_PATH.exists():
        config.read(USER_CONFIG_PATH)
    return config


def _write_fetch_defaults(config_path: str, local_path: str, save_logfile: bool) -> None:
    """Persist fetch defaults to user config file."""
    config = _read_user_config()
    if FETCH_SECTION not in config:
        config[FETCH_SECTION] = {}

    config[FETCH_SECTION]["config_path"] = config_path
    config[FETCH_SECTION]["local_path"] = local_path
    config[FETCH_SECTION]["save_logfile"] = str(save_logfile)

    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_CONFIG_PATH.open("w") as file_handle:
        config.write(file_handle)


def _resolve_fetch_settings(
    config_path: str | None,
    local_path: str | None,
    save_logfile: bool | None,
) -> tuple[str, str, bool]:
    """Resolve effective fetch settings from CLI args and INI defaults."""
    user_config = _read_user_config()
    resolved_config_path = config_path or user_config.get(
        FETCH_SECTION,
        "config_path",
        fallback=DEFAULT_FETCH_CONFIG_PATH,
    )
    resolved_local_path = local_path or user_config.get(
        FETCH_SECTION,
        "local_path",
        fallback=DEFAULT_FETCH_LOCAL_PATH,
    )

    if save_logfile is None:
        resolved_save_logfile = user_config.getboolean(
            FETCH_SECTION,
            "save_logfile",
            fallback=False,
        )
    else:
        resolved_save_logfile = save_logfile

    return resolved_config_path, resolved_local_path, resolved_save_logfile


@click.group(help="My personal work toolbox.")
def cli() -> None:
    """Top-level Click command group."""
    return None

@cli.command("hi", help="Print a quick greeting for CLI smoke testing.")
def hi_cmd() -> None:
    """Print a simple hi message."""
    try:
        click.echo("hi")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("clean_log", help="Find analytics.log and save analytics_filtered.log. Include words are positional; exclude words use --exclude.")
@click.option("--folder", default=".", show_default=True, help="Folder containing analytics.log")
@click.option(
    "--exclude",
    "exclude_words",
    multiple=True,
    help="Exclude lines containing these words. Repeat the option for multiple words.",
)
@click.argument("include_words", nargs=-1)
def clean_log_cmd(folder: str, exclude_words: tuple[str, ...], include_words: tuple[str, ...]) -> None:
    """Clean analytics.log in the given folder with include and exclude keyword sets."""
    try:
        output_file = clean_log_in_folder(
            folder=folder,
            include_keywords=include_words,
            exclude_keywords=exclude_words,
        )
        click.echo(f"Filtered log saved to: {output_file}")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("fetch_all_models", help="Download configured models from S3 to a local directory.")
@click.option("--config", "config_path", default=None, help="Path to the configuration file.")
@click.option("--local_path", default=None, help="Local directory where models are downloaded.")
@click.option("--force_download", is_flag=True, help="Force download even if local model path exists.")
@click.option("--save_logfile/--no-save_logfile", default=None, help="Enable or disable logfile persistence.")
def fetch_all_models_cmd(
    config_path: str | None,
    local_path: str | None,
    force_download: bool,
    save_logfile: bool | None,
) -> None:
    """Download all configured models from S3."""
    try:
        resolved_config_path, resolved_local_path, resolved_save_logfile = _resolve_fetch_settings(
            config_path=config_path,
            local_path=local_path,
            save_logfile=save_logfile,
        )

        _write_fetch_defaults(
            config_path=resolved_config_path,
            local_path=resolved_local_path,
            save_logfile=resolved_save_logfile,
        )

        click.echo("Using fetch_all_models settings:")
        click.echo(f"  config: {resolved_config_path}")
        click.echo(f"  local_path: {resolved_local_path}")
        click.echo(f"  save_logfile: {resolved_save_logfile}")
        click.echo(f"  user_ini: {USER_CONFIG_PATH}")

        count = fetch_all_models(
            config_path=resolved_config_path,
            local_path=resolved_local_path,
            force_download=force_download,
            save_logfile=resolved_save_logfile,
        )
        click.echo(f"Completed model fetch workflow. Models discovered: {count}")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def main() -> None:
    """Primary package entrypoint for the `ak-tools` command."""
    cli()

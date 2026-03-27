"""
Read the following:

click - group, command, option, argument, echo, ClickException
- click nested groups and commands 
"""

from __future__ import annotations

import click
import logging
import os.path as osp
import shutil
import sys

from .analytics_log_parser import clean_log_in_folder
from .clipboard import get_copy_aliases, try_copy_to_clipboard
from .config_manager import ConfigManager
from .model_fetcher import fetch_all_models
from ak_tools.change_configs import copy_section_to_other_configs
from .s3_presigner import main as s3_presigner_main
from .sync_alert import download_alerts, LOCAL_STORAGE_DIR

CONFIG_MANAGER = ConfigManager()
FETCH_SECTION = "fetch_all_models"
FETCH_DEFAULTS: dict[str, str | bool] = {
    "config_path": "/data4/ashok/REPROCESSING/analytics/src/nd_config_bagheera2_NA_US.ini",
    "local_path": "/data4/ashok/REPROCESSING/autocam",
    "save_logfile": False,
}


@click.group(help="My personal work toolbox.")
def cli() -> None:
    """Top-level Click command group."""
    return None

@cli.command("hi", help="Print a quick greeting for CLI smoke testing.")
def hi_cmd() -> None:
    """Print a simple hi message."""
    try:
        click.echo("hi bro!")
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
        resolved = CONFIG_MANAGER.resolve_and_persist(
            section=FETCH_SECTION,
            defaults=FETCH_DEFAULTS,
            overrides={
                "config_path": config_path,
                "local_path": local_path,
                "save_logfile": save_logfile,
            },
        )
        resolved_config_path = str(resolved["config_path"])
        resolved_local_path = str(resolved["local_path"])
        resolved_save_logfile = bool(resolved["save_logfile"])

        click.echo("Using fetch_all_models settings:")
        click.echo(f"  config: {resolved_config_path}")
        click.echo(f"  local_path: {resolved_local_path}")
        click.echo(f"  save_logfile: {resolved_save_logfile}")
        click.echo(f"  user_ini: {CONFIG_MANAGER.user_config_path}")

        count = fetch_all_models(
            config_path=resolved_config_path,
            local_path=resolved_local_path,
            force_download=force_download,
            save_logfile=resolved_save_logfile,
        )
        click.echo(f"Completed model fetch workflow. Models discovered: {count}")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("change_config", help="Copy one section from a source config into sibling nd_config_*.ini files.")
@click.argument("config_path", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option(
    "--section",
    "section_name",
    default="drowsy_sensor_fusion",
    show_default=True,
    help="Section name to copy (without brackets).",
)
def change_config_cmd(config_path: str, section_name: str) -> None:
    """Copy a section from one INI into all other sibling nd_config_*.ini files."""
    try:
        updated_count, scanned_count = copy_section_to_other_configs(config_path, section_name)
        click.echo(f"Section [{section_name}] copied from: {config_path}")
        click.echo(f"Target configs scanned: {scanned_count}")
        click.echo(f"Configs updated: {updated_count}")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cli.command("copy", help="Copy a configured alias to clipboard.")
@click.argument("alias", required=False)
def copy_cmd(alias: str | None) -> None:
    """Copy configured alias value to clipboard."""
    try:
        aliases = get_copy_aliases()

        if alias is None:
            if not aliases:
                click.echo("No aliases configured.")
                return

            for alias in aliases:
                click.echo(alias)
            return

        value = aliases.get(alias)
        if value is None:
            raise click.ClickException(
                f"Unknown alias: {alias}. Run `ak copy` to list aliases."
            )

        backend = try_copy_to_clipboard(value)
        if backend is not None:
            click.echo("Copied.")
            return

        click.echo("Clipboard unavailable.", err=True)
        click.echo(value)
        sys.exit(0)
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@cli.group("neo", help="Neokpi workflows and server commands.")
def neo_group() -> None:
    """Commands under ak neo."""
    return None


@neo_group.command("s3_presigner", help="Start the neokpi S3 file content server with local storage support.")
@click.option("--port", type=int, default=8080, show_default=True, help="Port to run the server on.")
@click.option("--host", default="localhost", show_default=True, help="Host to bind to.")
@click.option("--offline", is_flag=True, help="Run in offline mode (local storage only, no AWS).")
@click.option("--outdir", default=None, help="Output directory for metadata storage (optional, for custom lookups).")
def neo_s3_presigner_cmd(port: int, host: str, offline: bool, outdir: str | None) -> None:
    """Start the neokpi S3 file content downloader server."""
    try:
        # Convert Click arguments to argparse-like format for the original main function
        sys.argv = ["ak", "--port", str(port), "--host", host]
        if outdir:
            sys.argv.extend(["--outdir", outdir])
        if offline:
            sys.argv.append("--offline")
        s3_presigner_main()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@neo_group.command("add", help="Read alert ids/avids from a file (one per line) and download them.")
@click.argument("filepath", type=click.Path(exists=True, dir_okay=False, path_type=str))
@click.option("--alert_type", default=None, help="Optional input type override: alert_id, avid, or aaid.")
@click.option("--env", default="production", show_default=True, help="Environment for AVC API lookup.")
@click.option("--downscale/--no-downscale", default=False, show_default=True, help="Downscale mp4 files after download.")
def neo_add_cmd(filepath: str, alert_type: str | None, env: str, downscale: bool) -> None:
    """Download alerts listed in a file using sync_alert.download_alerts."""
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)-07s - %(name)-025s - %(message)s',
            stream=sys.stdout,
            force=True,
        )

        click.echo('Reminder: export AWS credentials before running this command if needed.')
        click.echo('Example: export AWS_ACCESS_KEY_ID="..."')
        click.echo('         export AWS_SECRET_ACCESS_KEY="..."')
        click.echo('         export AWS_SESSION_TOKEN="..."')

        with open(filepath, 'r', encoding='utf-8') as handle:
            alert_list = [
                line.strip() for line in handle
                if line.strip() and not line.strip().startswith('#')
            ]

        if not alert_list:
            raise click.ClickException(f'No alert IDs found in file: {filepath}')

        click.echo(f'Found {len(alert_list)} entries in {filepath}')
        download_alerts(
            alert_list,
            alert_type=alert_type,
            env=env,
            downscale=downscale,
        )
        click.echo('Done.')
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@neo_group.command("clean", help="Clear the local neokpi download storage.")
def neo_clean_cmd() -> None:
    """Clear LOCAL_STORAGE_DIR after confirmation."""
    try:
        if not osp.exists(LOCAL_STORAGE_DIR):
            click.echo(f'Nothing to clean. Directory does not exist: {LOCAL_STORAGE_DIR}')
            return

        confirmed = click.confirm(
            f'This will permanently delete: {LOCAL_STORAGE_DIR}. Continue?',
            default=False,
        )
        if not confirmed:
            click.echo('Cancelled.')
            return

        shutil.rmtree(LOCAL_STORAGE_DIR)
        click.echo(f'Cleared: {LOCAL_STORAGE_DIR}')
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def main() -> None:
    """Primary package entrypoint for the `ak-tools` command."""
    cli()

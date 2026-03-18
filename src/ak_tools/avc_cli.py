"""AVC API query command for the CLI."""

from __future__ import annotations

import click
import pandas as pd

from .avc_api import process_ids_from_file, sync_data


@click.command("avc", help="Query AVC API with IDs from a file or command-line arguments.")
@click.argument("id_values", nargs=-1)
@click.option("--file", "input_file", default=None, type=click.Path(exists=True), help="CSV file containing IDs to query.")
@click.option("--input_type", default="alert_id", show_default=True, help="Type of input ID (alert_id, aaid, avid, avsid, request_id).")
@click.option("--env", default="production", show_default=True, help="Environment (production or staging).")
@click.option("--processes", type=int, default=9, show_default=True, help="Number of parallel processes (file mode only).")
@click.option("--tail", type=int, default=None, help="Process only last N lines from file (optional).")
@click.option("--output", default=None, help="Output CSV filename.")
def avc_cmd(id_values: tuple[str, ...], input_file: str | None, input_type: str, env: str, processes: int, tail: int | None, output: str | None) -> None:
    """Query the AVC API with either IDs from a file or command-line arguments."""
    try:
        if input_file and id_values:
            raise click.ClickException("Cannot specify both --file and ID arguments")
        
        if not input_file and not id_values:
            raise click.ClickException("Must specify either --file or ID arguments")
        
        if input_file:
            # File mode
            click.echo(f"Starting AVC API query from file:")
            click.echo(f"  input_file: {input_file}")
            click.echo(f"  input_type: {input_type}")
            click.echo(f"  environment: {env}")
            click.echo(f"  processes: {processes}")
            if tail:
                click.echo(f"  processing last {tail} lines")
            click.echo()
            
            result_df = process_ids_from_file(
                input_file=input_file,
                input_type=input_type,
                env=env,
                num_processes=processes,
                tail_lines=tail,
                output_file=output,
            )
            click.echo(f"✓ AVC query completed successfully. Processed {len(result_df)} records.")
        else:
            # Direct IDs mode
            click.echo(f"Querying AVC API with {len(id_values)} ID(s):")
            click.echo(f"  input_type: {input_type}")
            click.echo(f"  environment: {env}")
            click.echo()
            
            results = []
            for idx, id_value in enumerate(id_values, 1):
                click.echo(f"[{idx}/{len(id_values)}] Querying {input_type}: {id_value}")
                result = sync_data(id_value, input_type, env)
                results.append(result)
            
            # Display results
            click.echo(f"\n{'=' * 60}")
            click.echo("Results:")
            click.echo(f"{'=' * 60}")
            for idx, result in enumerate(results, 1):
                click.echo(f"\n[{idx}] {input_type}: {id_values[idx-1]}")
                for key, value in result.items():
                    click.echo(f"  {key}: {value}")
            
            # Save to file if requested
            if output:
                result_df = pd.DataFrame(results)
                result_df.to_csv(output, index=False)
                click.echo(f"\n✓ Results saved to {output}")
            else:
                click.echo(f"\n✓ Query completed successfully for {len(id_values)} ID(s).")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


def main() -> None:
    """Primary entrypoint for the `avc` command."""
    avc_cmd()

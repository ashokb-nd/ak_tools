# ak_tools

Personal Python library template using a modern `src` layout and `pyproject.toml` packaging.

### What this is

- Reusable personal Python toolbox
- Install once in editable mode, use from anywhere
- Includes a CLI (`ak`) + importable modules

### Quick setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Quick use

```bash
ak hi
ak clean_log

Minimal personal toolbox with two CLIs: `ak` and `avc`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Core commands

```bash
ak --help
ak hi
ak clean_log
ak fetch_all_models
ak change_config /path/to/nd_config_source.ini
ak copy
ak copy <alias-or-text>
ak neo add <id1> <id2>
ak neo add --file /path/to/ids.txt
ak neo [--port PORT] [--host HOST] [--offline] [--outdir PATH]

avc --help
avc --input_type alert_id 12345
avc --file /path/to/ids.csv --input_type alert_id --output results.csv
```

## Notes

- `ak clean_log` writes `analytics_filtered.log`.
- `ak fetch_all_models` persists defaults in `~/.ak_tools/config.ini`.
- `ak copy` lists aliases when run without arguments.
- `ak neo add` accepts direct IDs, `--file`, or both.
- `avc` accepts either direct IDs or `--file` (not both).
- `ak neo` starts an S3 file content downloader server with local storage caching.

### Storage Location for `ak neo`

The `ak neo` command caches metadata files in `~/.neokpi_storage/`:

```
~/.neokpi_storage/
├── {alert_id_1}.json
├── {alert_id_2}.json
└── ...
```

**Default behavior:**
- All cached files are stored in `~/.neokpi_storage/` by default
- The `--outdir` flag is optional and used for additional custom metadata lookup paths

**Example usage:**
```bash
ak neo                                          # Default: localhost:8080, cache at ~/.neokpi_storage/
ak neo --port 9000                             # Custom port
ak neo --host 0.0.0.0                          # Accessible from network
ak neo --offline                               # Local storage only (no AWS)
ak neo --outdir /custom/path/to/metadata       # Check custom path first, then fall back to ~/.neokpi_storage/
```

## Shell autocomplete

### bash

```bash
echo 'eval "$(_AK_COMPLETE=bash_source ak)"' >> ~/.bashrc
echo 'eval "$(_AVC_COMPLETE=bash_source avc)"' >> ~/.bashrc
# ak_tools

Minimal personal toolbox with two CLIs: `ak` and `avc`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Core commands

```bash
ak --help
ak hi
ak clean_log
ak fetch_all_models
ak change_config /path/to/nd_config_source.ini
ak copy
ak copy <alias>

avc --help
avc --input_type alert_id 12345
avc --file /path/to/ids.csv --input_type alert_id --output results.csv
```

## Notes

- `ak clean_log` writes `analytics_filtered.log`.
- `ak fetch_all_models` persists defaults in `~/.ak_tools/config.ini`.
- `ak copy` lists aliases when run without arguments and errors for unknown aliases.
- `avc` accepts either direct IDs or `--file` (not both).

## Shell autocomplete

### bash

```bash
echo 'eval "$(_AK_COMPLETE=bash_source ak)"' >> ~/.bashrc
echo 'eval "$(_AVC_COMPLETE=bash_source avc)"' >> ~/.bashrc
source ~/.bashrc
```

### zsh

```bash
echo 'eval "$(env _AK_COMPLETE=zsh_source ak)"' >> ~/.zshrc
echo 'eval "$(env _AVC_COMPLETE=zsh_source avc)"' >> ~/.zshrc
source ~/.zshrc
```


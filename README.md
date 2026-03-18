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

avc --help
avc --input_type alert_id 12345
avc --file /path/to/ids.csv --input_type alert_id --output results.csv
```

## Notes

- `ak clean_log` writes `analytics_filtered.log`.
- `ak fetch_all_models` persists defaults in `~/.ak_tools/config.ini`.
- `ak copy` lists aliases when run without arguments.
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


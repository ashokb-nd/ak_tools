# ak_tools

Personal Python library template using a modern `src` layout and `pyproject.toml` packaging.

## Part 1: Crisp

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
ak clean_log drowsy_moderate --exclude heartbeat --exclude debug
ak fetch_all_models --config /path/to/config.ini --local_path /path/to/local_models
ak fetch_all_models --config /path/to/config.ini --local_path /path/to/local_models --force_download
ak fetch_all_models --config /path/to/config.ini --local_path /path/to/local_models --save_logfile
ak fetch_all_models

# standalone AVC command
avc --help
avc --input_type aaid 27810b25-b435-4108-b04f-9aafca0aec85
avc --input_type alert_id 12345 67890
avc --file /path/to/ids.csv --input_type alert_id --processes 9 --tail 1000 --output results.csv
```

`ak clean_log` writes output to `analytics_filtered.log`.

```python
from ak_tools import __version__

print(__version__)
```

---

## Part 2: Detailed

### Project structure

```text
ak_tools/
├── src/
│   └── ak_tools/
│       ├── __init__.py
│       ├── analytics_log_parser.py
│       ├── avc_api.py
│       ├── avc_cli.py
│       ├── cli.py
│       ├── config_manager.py
│       └── model_fetcher.py
├── pyproject.toml
└── README.md
```

### Setup steps

1. Create and activate a virtual environment.
2. Install the project in editable mode:

```bash
pip install -e .
```

### Usage

#### Import from Python

```python
from ak_tools import __version__

print(__version__)
```

#### Run the CLI

After editable install, these commands are available:

```bash
ak --help
ak hi
ak clean_log
ak clean_log drowsy_moderate --exclude heartbeat --exclude debug
ak fetch_all_models --config /path/to/config.ini --local_path /path/to/local_models
ak fetch_all_models --config /path/to/config.ini --local_path /path/to/local_models --force_download
ak fetch_all_models --config /path/to/config.ini --local_path /path/to/local_models --save_logfile
ak fetch_all_models

avc --help
avc --input_type aaid 27810b25-b435-4108-b04f-9aafca0aec85
avc --input_type alert_id 12345 67890
avc --file /path/to/ids.csv --input_type alert_id --processes 9 --tail 1000 --output results.csv
```

`ak fetch_all_models` stores defaults in `~/.ak_tools/config.ini` and prints effective values every run.

`avc` accepts either direct IDs or `--file` input (not both in the same call).

#### fetch_all_models INI defaults

- Precedence: CLI flags > `~/.ak_tools/config.ini` > built-in defaults.
- Built-in defaults:
	- `config_path`: `/data4/ashok/REPROCESSING/analytics/src/nd_config_bagheera2_NA_US.ini`
	- `local_path`: `/data4/ashok/REPROCESSING/autocam`
	- `save_logfile`: `False`

Example INI:

```ini
[fetch_all_models]
config_path = /data4/ashok/REPROCESSING/analytics/src/nd_config_bagheera2_NA_US.ini
local_path = /data4/ashok/REPROCESSING/autocam
save_logfile = False
```

### Cleanup

```bash
# remove generated fetch log (if --save_logfile was used)
rm -f fetch_all_models.log

# remove persisted CLI defaults
rm -f ~/.ak_tools/config.ini

# remove downloaded model directory (example)
rm -rf /path/to/local_models
```

#### Shell autocompletion (zsh)

```bash
echo 'eval "$(env _AK_COMPLETE=zsh_source ak)"' >> ~/.zshrc
source ~/.zshrc
```

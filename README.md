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
│       ├── cli.py
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
```

`ak fetch_all_models` stores defaults in `~/.ak_tools/config.ini` and prints effective values every run.

#### fetch_all_models INI defaults

- Precedence: CLI flags > `~/.ak_tools/config.ini` > built-in defaults.
- Built-in defaults:
	- `config_path`: `/data4/ashok/REPROCESSING/analytics/src/nd_config_bagheera2_US.ini`
	- `local_path`: `/data4/ashok/REPROCESSING/autocam`
	- `save_logfile`: `False`

Example INI:

```ini
[fetch_all_models]
config_path = /data4/ashok/REPROCESSING/analytics/src/nd_config_bagheera2_US.ini
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

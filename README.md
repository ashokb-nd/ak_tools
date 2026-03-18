# ak_tools

Personal Python library template using a modern `src` layout and `pyproject.toml` packaging.

## Part 1: Crisp

### What this is

- Reusable personal Python toolbox
- Install once in editable mode, use from anywhere
- Includes a CLI (`ak-tools`) + importable modules

### Quick setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Quick use

```bash
ak-tools hi
ak-tools process --input data.csv --deviation 0.24 --decay 0.1
```

```python
from ak_tools import hi, calculate_lane_score

hi()
print(calculate_lane_score(0.24))
```

---

## Part 2: Detailed

### Project structure

```text
ak_tools/
├── src/
│   └── ak_tools/
│       ├── __init__.py
│       ├── cli.py
│       ├── data_utils.py
│       └── plot_helper.py
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
from ak_tools.data_utils import calculate_lane_score

score = calculate_lane_score(0.24)
print(score)
```

#### Run the CLI

After editable install, these commands are available:

```bash
ak-tools --help
ak-tools hi
ak-tools process --input data.csv --threshold 0.5 --deviation 0.24 --decay 0.1
ak-tools analyze --source prepared.csv
ak-tools report --output report.md
```

Backward-compatible command alias:

```bash
process-data --input data.csv --deviation 0.24 --decay 0.1
```

#### Shell autocompletion (zsh)

```bash
echo 'eval "$(env _AK_TOOLS_COMPLETE=zsh_source ak-tools)"' >> ~/.zshrc
source ~/.zshrc
```

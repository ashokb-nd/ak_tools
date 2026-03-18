"""Download analytics model weights from s3
"""

from __future__ import annotations

import configparser
import logging
import subprocess
from pathlib import Path

BASE_AWS_PATH = "analytics/models/"
BUCKET_NAME = "netradyne-sharing"
LOG_FILE_NAME = "fetch_all_models.log"


def _get_logger(save_logfile: bool = False) -> logging.Logger:
    """Create a module logger with console handler and optional file handler."""
    logger = logging.getLogger("ak_tools.model_fetcher")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if save_logfile and not any(isinstance(handler, logging.FileHandler) for handler in logger.handlers):
        file_handler = logging.FileHandler(LOG_FILE_NAME)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def load_config(config_path: str | Path) -> configparser.ConfigParser:
    """Load and validate a model configuration file."""
    logger = _get_logger()
    path = Path(config_path)
    if not path.exists():
        logger.error("Configuration file %s does not exist.", path)
        raise FileNotFoundError(f"Configuration file {path} not found.")

    config = configparser.ConfigParser()
    config.read(path)
    if "deviceModelFiles" not in config:
        logger.error("Configuration file is missing the 'deviceModelFiles' section.")
        raise ValueError("Invalid configuration file format.")
    return config


def _download_model(
    model: str,
    local_model_path: Path,
    s3_path: str,
    force_download: bool,
) -> None:
    """Download one model directory from S3."""
    logger = _get_logger()
    if local_model_path.exists() and not force_download:
        logger.info("Model %s already exists locally. Skipping download.", model)
        return

    local_model_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        logger.info("Downloading model %s from S3...", model)
        subprocess.run(
            [
                "aws",
                "s3",
                "cp",
                f"s3://{BUCKET_NAME}/{s3_path}",
                str(local_model_path),
                "--recursive",
            ],
            check=True,
        )
        if local_model_path.exists():
            logger.info("Model %s has been downloaded successfully.", model)
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to download model %s. Error: %s", model, exc)


def fetch_all_models(
    config_path: str | Path,
    local_path: str | Path,
    force_download: bool = False,
    save_logfile: bool = False,
) -> int:
    """Download all configured models and return the total count discovered."""
    logger = _get_logger(save_logfile=save_logfile)
    config = load_config(config_path)

    local_root = Path(local_path)
    local_root.mkdir(parents=True, exist_ok=True)

    model_list = [
        Path(path).name
        for key, path in config.items("deviceModelFiles")
        if key.endswith("_path") and path.strip()
    ]

    logger.info("Found %d models in the configuration file.", len(model_list))

    for model in model_list:
        local_model_path = local_root / model
        s3_path = f"{BASE_AWS_PATH}{model}"
        _download_model(model, local_model_path, s3_path, force_download)

    return len(model_list)

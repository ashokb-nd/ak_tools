"""Configuration management helpers for CLI commands."""

from __future__ import annotations

import configparser
from pathlib import Path
from typing import Mapping


class ConfigManager:
    """Generic configuration manager for resolving and persisting section values."""

    def __init__(self, user_config_path: Path | None = None) -> None:
        self.user_config_path = user_config_path or (Path.home() / ".ak_tools" / "config.ini")

    def _read_user_config(self) -> configparser.ConfigParser:
        """Read user-level config if present."""
        config = configparser.ConfigParser()
        if self.user_config_path.exists():
            config.read(self.user_config_path)
        return config

    def resolve_and_persist(
        self,
        section: str,
        defaults: Mapping[str, str | bool],
        overrides: Mapping[str, str | bool | None],
    ) -> dict[str, str | bool]:
        """Resolve effective values and persist them for a config section."""
        config = self._read_user_config()
        if section not in config:
            config[section] = {}

        resolved: dict[str, str | bool] = {}
        ordered_keys = list(dict.fromkeys([*defaults.keys(), *overrides.keys()]))

        for key in ordered_keys:
            override_value = overrides.get(key)
            if override_value is not None:
                value: str | bool = override_value
            else:
                default_value = defaults.get(key, "")
                if isinstance(default_value, bool):
                    value = config.getboolean(section, key, fallback=default_value)
                else:
                    value = config.get(section, key, fallback=str(default_value))

            resolved[key] = value
            config[section][key] = str(value)

        self.user_config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.user_config_path.open("w") as file_handle:
            config.write(file_handle)

        return resolved

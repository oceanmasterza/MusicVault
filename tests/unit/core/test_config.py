"""Unit tests for musicvault.core.config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from musicvault.core.config import (
    CURRENT_SCHEMA_VERSION,
    AppConfig,
    default_config,
    load_config,
    save_config,
)
from musicvault.core.exceptions import ConfigError, ConfigVersionError


def test_default_config_uses_current_schema_version() -> None:
    assert default_config().schema_version == CURRENT_SCHEMA_VERSION


def test_load_config_creates_default_file_when_missing(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    assert not config_path.exists()

    config = load_config(config_path)

    assert config == default_config()
    assert config_path.exists()


def test_load_config_round_trips_saved_values(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    original = AppConfig(log_level="DEBUG", theme="light")
    save_config(original, config_path)

    loaded = load_config(config_path)

    assert loaded == original


def test_load_config_rejects_invalid_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_non_object_json(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_config_rejects_missing_schema_version(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"log_level": "INFO"}), encoding="utf-8")

    with pytest.raises(ConfigVersionError):
        load_config(config_path)


def test_load_config_rejects_future_schema_version(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"schema_version": CURRENT_SCHEMA_VERSION + 1}), encoding="utf-8"
    )

    with pytest.raises(ConfigVersionError):
        load_config(config_path)


def test_load_config_ignores_unknown_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"schema_version": CURRENT_SCHEMA_VERSION, "future_field": "x"}),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.schema_version == CURRENT_SCHEMA_VERSION


def test_save_config_writes_pretty_printed_utf8_json(tmp_path: Path) -> None:
    config_path = tmp_path / "nested" / "config.json"
    save_config(default_config(), config_path)

    text = config_path.read_text(encoding="utf-8")
    assert json.loads(text) == default_config().to_dict()


def test_shipped_defaults_json_matches_code_defaults() -> None:
    """The repository's config/defaults.json must stay in sync with AppConfig()."""
    defaults_path = Path(__file__).parents[3] / "config" / "defaults.json"
    shipped = json.loads(defaults_path.read_text(encoding="utf-8"))

    assert shipped == default_config().to_dict()

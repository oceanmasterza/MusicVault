"""Unit tests for musicvault.core.exceptions."""

from __future__ import annotations

import pytest

from musicvault.core.exceptions import (
    ConfigError,
    ConfigMigrationError,
    ConfigVersionError,
    MusicVaultError,
    PluginError,
    PluginLoadError,
)


@pytest.mark.parametrize(
    "exception_type",
    [ConfigError, ConfigVersionError, ConfigMigrationError, PluginError, PluginLoadError],
)
def test_all_exceptions_derive_from_musicvault_error(exception_type: type[Exception]) -> None:
    assert issubclass(exception_type, MusicVaultError)


def test_config_version_error_derives_from_config_error() -> None:
    assert issubclass(ConfigVersionError, ConfigError)


def test_plugin_load_error_message_includes_plugin_id_and_cause() -> None:
    cause = ValueError("bad api key")

    error = PluginLoadError("musicbrainz", cause)

    assert "musicbrainz" in str(error)
    assert "bad api key" in str(error)
    assert error.plugin_id == "musicbrainz"
    assert error.cause is cause

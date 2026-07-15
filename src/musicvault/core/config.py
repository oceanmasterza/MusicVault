"""Versioned JSON application configuration.

Configuration is stored as a single JSON document at
``AppPaths.config_file``. Every serialized document carries a
``schema_version`` field. On load, older documents are migrated forward
through a chain of pure functions registered in ``_MIGRATIONS`` until they
reach :data:`CURRENT_SCHEMA_VERSION`, so upgrading MusicVault never
requires the user to manually edit or delete their configuration file.

The :class:`AppConfig` dataclass intentionally stays small in Phase 1.
Sections that configure entities which do not exist yet — library zones,
watch-folder behaviour, metadata provider priority, rules — are added in
the phases that introduce those entities (see
docs/architecture/07-roadmap.md) rather than being stubbed out here
unused.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from musicvault.core.exceptions import ConfigError, ConfigMigrationError, ConfigVersionError

CURRENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class AppConfig:
    """Root application configuration."""

    schema_version: int = CURRENT_SCHEMA_VERSION
    log_level: str = "INFO"
    theme: str = "dark"

    def to_dict(self) -> dict[str, Any]:
        """Return a plain-dict representation suitable for JSON serialization."""
        return asdict(self)


def default_config() -> AppConfig:
    """Return the built-in default configuration."""
    return AppConfig()


# Each migration receives the raw dict at version N and must return a new
# dict upgraded to version N + 1, including the updated 'schema_version'
# key. Register a new entry here every time CURRENT_SCHEMA_VERSION is
# incremented; never mutate a past migration once it has shipped.
_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def _migrate(raw: dict[str, Any]) -> dict[str, Any]:
    version = raw.get("schema_version")
    if not isinstance(version, int):
        raise ConfigVersionError(
            f"Configuration is missing a valid integer 'schema_version' field: {version!r}"
        )
    if version > CURRENT_SCHEMA_VERSION:
        raise ConfigVersionError(
            f"Configuration schema version {version} is newer than this build of MusicVault "
            f"supports (current: {CURRENT_SCHEMA_VERSION}). Update the application."
        )

    while version < CURRENT_SCHEMA_VERSION:
        migration = _MIGRATIONS.get(version)
        if migration is None:
            raise ConfigMigrationError(
                f"No migration registered to upgrade configuration from version {version}."
            )
        raw = migration(raw)
        version = raw["schema_version"]

    return raw


def _from_dict(raw: dict[str, Any]) -> AppConfig:
    known_fields = set(AppConfig.__dataclass_fields__)
    filtered = {key: value for key, value in raw.items() if key in known_fields}
    return AppConfig(**filtered)


def load_config(path: Path) -> AppConfig:
    """Load configuration from ``path``, creating it with defaults if missing.

    Raises:
        ConfigError: if the file exists but contains invalid JSON, or its
            contents are not a JSON object.
        ConfigVersionError: if the schema version is missing, malformed, or
            newer than this build supports.
        ConfigMigrationError: if migrating an older schema version fails.
    """
    if not path.exists():
        config = default_config()
        save_config(config, path)
        return config

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Configuration file at {path} is not valid JSON: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"Configuration file at {path} must contain a JSON object.")

    migrated = _migrate(raw)
    config = _from_dict(migrated)

    if migrated is not raw:
        # A migration ran — persist the upgraded document immediately so
        # the on-disk file never silently lags behind the in-memory value.
        save_config(config, path)

    return config


def save_config(config: AppConfig, path: Path) -> None:
    """Serialize ``config`` to ``path`` as pretty-printed JSON (UTF-8)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    document = json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n"
    path.write_text(document, encoding="utf-8")

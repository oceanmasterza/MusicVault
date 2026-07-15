"""Unit tests for musicvault.core.container."""

from __future__ import annotations

from musicvault.core.config import AppConfig
from musicvault.core.container import Container
from musicvault.core.event_bus import EventBus
from musicvault.core.paths import AppPaths


def test_bootstrap_wires_provided_paths_and_config(
    app_paths: AppPaths, app_config: AppConfig
) -> None:
    container = Container.bootstrap(paths=app_paths, config=app_config)

    assert container.paths is app_paths
    assert container.config is app_config


def test_bootstrap_creates_an_event_bus(app_paths: AppPaths, app_config: AppConfig) -> None:
    container = Container.bootstrap(paths=app_paths, config=app_config)

    assert isinstance(container.event_bus, EventBus)


def test_each_bootstrap_call_creates_an_independent_event_bus(
    app_paths: AppPaths, app_config: AppConfig
) -> None:
    first = Container.bootstrap(paths=app_paths, config=app_config)
    second = Container.bootstrap(paths=app_paths, config=app_config)

    assert first.event_bus is not second.event_bus

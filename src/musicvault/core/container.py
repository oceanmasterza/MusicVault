"""Application-wide dependency injection container.

A single :class:`Container` instance is created during application
bootstrap (see :mod:`musicvault.app`) and threaded through explicitly to
whatever needs it. There is no module-level singleton, which keeps every
component trivially testable: a test builds its own container from a
temporary directory and an in-memory configuration instead of relying on
global state.

Later phases extend this container with the database engine, job queue
manager, plugin manager, and application services as those layers are
implemented (see docs/architecture/07-roadmap.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from musicvault.core.config import AppConfig
from musicvault.core.event_bus import EventBus
from musicvault.core.paths import AppPaths


@dataclass
class Container:
    """Holds the fully wired set of application-level dependencies."""

    paths: AppPaths
    config: AppConfig
    event_bus: EventBus = field(default_factory=EventBus)

    @classmethod
    def bootstrap(cls, *, paths: AppPaths, config: AppConfig) -> Container:
        """Construct a container for normal application startup."""
        return cls(paths=paths, config=config)

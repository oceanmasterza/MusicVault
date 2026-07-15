# Changelog

All notable changes to MusicVault are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Phase 1 project scaffold** — first runnable application code:
  - `src/musicvault/` package skeleton following the v3 folder layout
    (`models/`, `core/`, `db/`, `services/`, `workers/`, `plugins/`, `gui/`)
  - `core/exceptions.py` — application exception hierarchy
  - `core/paths.py` — cross-platform app data directory resolution
    (`%APPDATA%/MusicVault` on Windows)
  - `core/config.py` — versioned JSON configuration with migration chain
  - `core/logging.py` — Loguru sinks (console, `musicvault.log`, `debug.log`, crash logs)
  - `core/event_bus.py` — thread-safe publish/subscribe for domain events
  - `core/container.py` — dependency injection container
  - `app.py` — application bootstrap sequence
  - `__main__.py` — `python -m musicvault` / `musicvault` CLI entry point
  - `config/defaults.json` — default configuration template
  - 43 tests (unit + integration), 97% coverage
  - `pyproject.toml` with full dependency set and tool configuration
    (ruff, black, mypy strict, import-linter, pytest)
  - `.github/workflows/ci.yml` — lint, typecheck, and test on every push/PR
  - `.github/workflows/release.yml` — PyInstaller build on version tags
  - `CONTRIBUTING.md` — development setup and contribution guidelines
- Architecture v3 pipeline engine refinements ([12-pipeline-engine-v3.md](docs/architecture/12-pipeline-engine-v3.md)):
  - Dedicated single-writer DB queue (eliminates SQLite lock contention)
  - ProcessPool for CPU-bound workers (hash, fingerprint, audio parse)
  - ThreadPool for I/O-bound workers (scan, HTTP, file ops)
  - Event bus + Qt bridge for GUI decoupling
  - UUID v7 stored as BLOB(16) instead of TEXT(36)
  - Batch writes increased to 5,000–10,000 rows
  - Adaptive mmap sizing (not fixed 30 GB)
  - Dual metadata cascades (identification vs enrichment)
  - Composite confidence scoring formula
  - Rules engine AST evaluation spec
  - Folder layout renamed: models/, services/, db/, workers/
- Updated performance strategy and folder layout for v3

### Changed

- Navidrome integration explicitly read-only for DB (writes via API only)
- UUID v4 recommendation evaluated; v7 retained for index locality

### Added (v2)
  - Scalability risk review (10 risks identified and mitigated)
  - SQLAlchemy Core instead of ORM
  - UUID v7 primary keys for all entities
  - Persistent job queue with independent workers
  - Metadata arbitration with per-field confidence scoring
  - Review queue for uncertain matches (< 90% threshold)
  - Staging library (Incoming → Staging → Review → Library)
  - User-configurable rules engine
  - Watch folder with zero-click automation pipeline
  - Fingerprint/hash persistence with skip-if-unchanged logic
  - Visual duplicate viewer design
  - 10 media server plugins (Navidrome with direct DB access)
  - CI pipeline specification (GitHub Actions from Phase 1)
- Updated all architecture documents (01–07) for v2 consistency
- New documents: 10-revision-v2.md, 11-ci-pipeline.md

### Changed

- Database schema: integer IDs → UUID v7; added jobs, review_items, rules, file_identity tables
- Service layer: monolithic services → job queue + worker architecture
- Plugin API: expanded from 4 to 10 media servers; metadata providers return confidence scores
- GUI: added Review Queue, Job Monitor, Rules Editor, Duplicate Viewer pages
- Roadmap: 14 phases → 16 phases; CI moved from Phase 14 to Phase 1
- Target users: expanded media server list (Jellyfin, Plex, Emby, Ampache, Koel, etc.)

## [0.0.0] - 2026-07-15

### Added

- Project inception — architecture phase only, no application code

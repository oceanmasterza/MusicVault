# MusicVault

**Lightroom for Music** — a professional, open-source Windows application for managing large music libraries with self-hosted media servers.

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

## Vision

MusicVault automates the complete lifecycle of a music library:

- **Watch folder** — drop files in Incoming; hashing, identification, and artwork run in place
- **Fingerprint** — Chromaprint + AcoustID identification (full or album-folder sampling)
- **Multi-provider metadata** — MusicBrainz, AcoustID, local tags, filenames, ranked by confidence
- **Review queue** — uncertain matches need approval before entering the canonical library
- **Rules engine** — configurable IF/THEN automation (archive MP3 when FLAC exists, etc.)
- **Single move to Library** — originals stay in Incoming until confirmed, then one organize step
- **Incoming cleanup** — leftover `.nfo` / covers / empty album folders are removed after the last audio file moves
- **Detect duplicates** — album-aware matching; confident same-album dups can auto-resolve
- **Organize & rename** — `Artist / Year - Album / track` under Library
- **Artwork** — embedded covers preferred; Cover Art Archive when needed; album-level reuse
- **Browse UI** — Library folder tree, Artists, Albums, Artwork status
- **Media server integration** — Navidrome, Jellyfin, Plex, Subsonic rescan after library entry
- **Rollback** — organize moves are reversible via operation snapshots

Designed for power users with libraries of **100,000–1,000,000+ tracks**.

## Target Users

Collectors, audiophiles, and self-hosted media server operators using **Navidrome**, **Jellyfin**, **Plex**, **Emby**, **Ampache**, **Koel**, **Subsonic**, **Funkwhale**, **Lyrion Music Server**, or **mStream**.

## Status

**1.0-capable — Phases 1–16 delivered**

The full pipeline runs end-to-end:

`scan → hash → fingerprint → identify → duplicates → rules → organize → artwork / media-server sync`

with review, rollback, reports, Dashboard, and browse pages. Install with the
Windows Setup (`packaging/output/MusicVault-Setup.exe`) — Chromaprint
(`fpcalc`) is bundled. See [Architecture Documentation](docs/architecture/README.md)
and [packaging/README.md](packaging/README.md).

```powershell
git clone https://github.com/oceanmasterza/MusicVault.git
cd MusicVault
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,build]"
pytest
python -m musicvault          # GUI
# CI / automation: python -m musicvault --headless
.\packaging\build_windows.ps1 # rebuild Setup.exe
```

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.14 |
| GUI | PySide6 (Qt6) |
| Database | SQLite + **SQLAlchemy Core** (not ORM) |
| Identities | **UUID v7** (all entities) |
| Processing | **Persistent job queue** with independent workers |
| Audio metadata | Mutagen |
| Identification | MusicBrainz, AcoustID, Chromaprint |
| Fuzzy matching | RapidFuzz |
| Logging | Loguru |
| Testing | pytest + mypy strict |
| CI | GitHub Actions (ruff, black, mypy, pytest) |
| Packaging | PyInstaller + Setup.exe |

## Architecture Highlights (v3)

| Decision | Choice | Why |
|----------|--------|-----|
| Database access | SQLAlchemy Core | 3–5× faster than ORM at 1M+ rows |
| Writes | Single-writer DB thread | Eliminates SQLite lock contention |
| CPU-bound work | ProcessPool (threads in frozen builds) | Hashing / fingerprinting |
| Processing | Job queue + workers | Resumable, crash-safe, observable |
| Metadata | Multi-provider arbitration | No single source of truth |
| Uncertain data | Review queue (configurable threshold) | Prevents metadata corruption |
| File placement | In-place Incoming → one Library move | Mistakes don't touch the canonical tree early |
| Automation | Rules engine + watch folder | Zero-click processing |
| CI | From Phase 1 | No broken commits from day one |

## Documentation

| Document | Description |
|----------|-------------|
| **[Pipeline Engine v3](docs/architecture/12-pipeline-engine-v3.md)** | DB writer, ProcessPool, event bus |
| [Revision v2](docs/architecture/10-revision-v2.md) | Job queue, UUID, review, staging |
| [Overview](docs/architecture/01-overview.md) | Job pipeline, library zones |
| [Folder Layout](docs/architecture/02-folder-layout.md) | `models/`, `core/`, `db/`, `services/`, `workers/` |
| [Database Schema](docs/architecture/03-database-schema.md) | UUID schema, jobs, review queue |
| [Service Layer](docs/architecture/04-service-layer.md) | Job queue, arbitrator, rules |
| [Plugin API](docs/architecture/05-plugin-api.md) | Metadata, artwork, media servers |
| [GUI Architecture](docs/architecture/06-gui-architecture.md) | Sidebar pages, Review UX |
| [Roadmap](docs/architecture/07-roadmap.md) | 16-phase plan + post-MVP polish |
| [CI Pipeline](docs/architecture/11-ci-pipeline.md) | GitHub Actions spec |
| [Packaging](packaging/README.md) | Windows Setup build |

## Development Roadmap (Summary)

| Phase | Milestone | Status |
|-------|-----------|--------|
| 0–0b | Architecture v1 / v2 | Complete |
| 1–12 | Scaffold → Rollback | Complete |
| 13 | Reports | Complete |
| 14 | GUI (Dashboard, Library tree, Artists/Albums/Artwork, Review, Jobs, …) | Complete |
| 15 | Media server plugins | Complete |
| 16 | Windows installer (bundled fpcalc) | Complete |
| Next | Plugin manager UI, Discogs, deeper browse polish | Planned |

## License

MIT License — see [LICENSE](LICENSE).

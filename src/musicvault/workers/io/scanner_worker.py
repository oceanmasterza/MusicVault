"""ScannerWorker — directory walking for the `scan_directory` job.

I/O-bound (Tier 2 — see docs/architecture/08-performance.md, "Three-Tier
Worker Model"), so unlike :mod:`musicvault.workers.cpu.hash_worker` this
runs on a `ThreadPoolExecutor` thread and can hold live repository/writer
references directly — threads share the parent process's memory, so
nothing needs to cross a pickling boundary here.

`Job.payload` contract for `scan_directory`: ``{"directory": str,
"zone": str}`` (a `LibraryZone` value) — not specified by name in the
architecture docs beyond "the path", so this module defines it. The
target library is `Job.library_id` itself, not part of the payload.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from loguru import logger

from musicvault.db.repositories.file_identity_repo import FileIdentityRepository
from musicvault.db.repositories.track_repo import TrackRepository
from musicvault.db.uuid_utils import generate_uuid7
from musicvault.db.writer import DatabaseWriter, WriteDTO
from musicvault.models.entities.job import Job, JobType
from musicvault.models.entities.track import LibraryZone, Track
from musicvault.services.job_queue_service import JobQueueService

_AUDIO_EXTENSIONS = frozenset(
    {".flac", ".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".wma", ".ape", ".wv"}
)
"""Not enumerated anywhere in the architecture docs — a reasonable,
documented fill-in covering the formats already named elsewhere in the
codebase (FLAC/MP3/AAC in `QualityScorer`) plus the other common lossy
and lossless container/codec extensions a real library would contain."""


class ScannerWorker:
    """Executes one `scan_directory` job: walks the directory, and for
    every audio file whose size/mtime differ from what's already
    recorded (or that's never been seen before), upserts a `Track` row
    and enqueues a `hash_file` job for it.
    """

    def __init__(
        self,
        track_repo: TrackRepository,
        file_identity_repo: FileIdentityRepository,
        database_writer: DatabaseWriter,
        job_queue: JobQueueService,
    ) -> None:
        self._track_repo = track_repo
        self._file_identity_repo = file_identity_repo
        self._writer = database_writer
        self._job_queue = job_queue

    def execute(self, job: Job) -> None:
        directory = Path(job.payload["directory"])
        zone = LibraryZone(job.payload["zone"])

        if not directory.is_dir():
            # `Path.rglob` silently yields nothing for a missing directory
            # rather than raising — checked explicitly so a mistyped or
            # since-removed library path fails loudly instead of "completing"
            # a scan that quietly found and did nothing.
            self._job_queue.mark_failed(job.id, f"{directory} is not a directory")
            return

        try:
            audio_files = list(_iter_audio_files(directory))
        except OSError as exc:
            self._job_queue.mark_failed(job.id, f"Failed to list {directory}: {exc}")
            return

        for path in audio_files:
            self._process_file(job, path, zone)

        self._job_queue.mark_completed(job.id)

    def _process_file(self, job: Job, path: Path, zone: LibraryZone) -> None:
        try:
            stat = path.stat()
        except OSError as exc:
            logger.warning("Skipping {} — could not stat it: {}", path, exc)
            return

        existing = self._track_repo.get_by_path(str(path))
        track_id = existing.id if existing is not None else generate_uuid7()
        file_modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)

        if existing is not None:
            identity = self._file_identity_repo.get(track_id)
            if identity is not None and identity.matches_current_file(
                file_size=stat.st_size, file_modified=file_modified
            ):
                return  # unchanged — hash/fingerprint/metadata can all be skipped

        track = _build_track(
            existing,
            track_id=track_id,
            library_id=job.library_id,
            zone=zone,
            path=path,
            file_size=stat.st_size,
            file_modified=file_modified,
        )
        self._writer.submit(
            WriteDTO(table="tracks", operation="upsert", rows=[TrackRepository.to_row(track)])
        )
        self._job_queue.enqueue(
            JobType.HASH_FILE,
            job.library_id,
            {"track_id": str(track_id), "file_path": str(path)},
            parent_job_id=job.id,
        )


def _iter_audio_files(directory: Path) -> Iterator[Path]:
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix.lower() in _AUDIO_EXTENSIONS:
            yield path


def _build_track(
    existing: Track | None,
    *,
    track_id: UUID,
    library_id: UUID,
    zone: LibraryZone,
    path: Path,
    file_size: int,
    file_modified: datetime,
) -> Track:
    """A brand-new file gets a fresh `Track`; a re-scanned known file
    keeps every previously arbitrated field (title, artist, quality
    score, ...) and only refreshes what the filesystem can tell us —
    `TrackRepository.upsert_batch`'s underlying `batch_upsert` overwrites
    *every* column on conflict, so silently dropping the other fields
    here would erase metadata a later phase's MetadataWorker already
    filled in.
    """
    if existing is not None:
        return replace(
            existing,
            file_path=str(path),
            file_name=path.name,
            file_size=file_size,
            file_modified=file_modified,
            updated_at=datetime.now(UTC),
        )
    now = datetime.now(UTC)
    return Track(
        id=track_id,
        library_id=library_id,
        zone=zone,
        file_path=str(path),
        file_name=path.name,
        file_size=file_size,
        file_modified=file_modified,
        created_at=now,
        updated_at=now,
    )

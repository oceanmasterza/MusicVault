"""Application-wide dependency injection container.

A single :class:`Container` instance is created during application
bootstrap (see :mod:`musicvault.app`) and threaded through explicitly to
whatever needs it. There is no module-level singleton, which keeps every
component trivially testable: a test builds its own container from a
temporary directory and an in-memory configuration instead of relying on
global state.

Later phases extend this container with the plugin manager and
application services as those layers are implemented (see
docs/architecture/07-roadmap.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import Engine

from musicvault.core.config import AppConfig
from musicvault.core.event_bus import EventBus
from musicvault.core.paths import AppPaths
from musicvault.db.engine import create_sqlite_engine
from musicvault.db.migrations.runner import run_migrations
from musicvault.db.repositories.album_repo import AlbumRepository
from musicvault.db.repositories.artist_repo import ArtistRepository
from musicvault.db.repositories.file_identity_repo import FileIdentityRepository
from musicvault.db.repositories.job_repo import JobRepository
from musicvault.db.repositories.review_repo import ReviewRepository
from musicvault.db.repositories.rule_repo import RuleRepository
from musicvault.db.repositories.track_repo import TrackRepository
from musicvault.db.writer import DatabaseWriter
from musicvault.services.job_dispatcher import JobDispatcher
from musicvault.services.job_queue_service import JobQueueService
from musicvault.workers.cpu.fingerprint_worker import FingerprintWorker
from musicvault.workers.cpu.hash_worker import HashWorker
from musicvault.workers.io.scanner_worker import ScannerWorker


@dataclass
class Container:
    """Holds the fully wired set of application-level dependencies."""

    paths: AppPaths
    config: AppConfig
    engine: Engine
    job_repo: JobRepository
    review_repo: ReviewRepository
    rule_repo: RuleRepository
    file_identity_repo: FileIdentityRepository
    track_repo: TrackRepository
    album_repo: AlbumRepository
    artist_repo: ArtistRepository
    database_writer: DatabaseWriter
    job_queue: JobQueueService
    scanner_worker: ScannerWorker
    hash_worker: HashWorker
    fingerprint_worker: FingerprintWorker
    dispatcher: JobDispatcher
    event_bus: EventBus = field(default_factory=EventBus)

    @classmethod
    def bootstrap(cls, *, paths: AppPaths, config: AppConfig) -> Container:
        """Construct a container for normal application startup.

        Runs pending Alembic migrations first — this is how the database
        file and its schema get created on first run — then opens the
        (now up-to-date) database and wires the repositories that read
        and write it.

        Also starts the pipeline: the single-writer
        :class:`DatabaseWriter` thread and the :class:`JobDispatcher`
        polling loop. Crash recovery (resetting jobs orphaned by a
        previous crash back to `retry`) runs synchronously, before the
        dispatcher starts polling — see
        :meth:`~musicvault.services.job_dispatcher.JobDispatcher.recover`.
        Starting the dispatcher here is safe even though nothing enqueues
        jobs yet: `ThreadPoolExecutor`/`ProcessPoolExecutor`
        only spawn actual OS threads/processes lazily, on first
        `submit()`, so an idle dispatcher costs one lightweight polling
        thread and no worker processes.
        """
        run_migrations(paths.database_file)
        engine = create_sqlite_engine(paths.database_file)

        job_repo = JobRepository(engine)
        track_repo = TrackRepository(engine)
        file_identity_repo = FileIdentityRepository(engine)

        database_writer = DatabaseWriter(
            engine,
            batch_size=config.pipeline.db_writer_batch_size,
            flush_interval_ms=config.pipeline.db_writer_flush_interval_ms,
        )
        job_queue = JobQueueService(job_repo, config.pipeline)
        scanner_worker = ScannerWorker(track_repo, file_identity_repo, database_writer, job_queue)
        hash_worker = HashWorker(file_identity_repo, database_writer, job_queue)
        fingerprint_worker = FingerprintWorker(file_identity_repo, database_writer, job_queue)
        dispatcher = JobDispatcher(
            job_queue,
            scanner_worker,
            hash_worker,
            fingerprint_worker,
            scanner_threads=config.pipeline.scanner_worker_threads,
            hash_processes=config.pipeline.hash_worker_processes,
            claim_batch_size=config.pipeline.job_claim_batch_size,
        )

        database_writer.start()
        dispatcher.recover()
        dispatcher.start()

        return cls(
            paths=paths,
            config=config,
            engine=engine,
            job_repo=job_repo,
            review_repo=ReviewRepository(engine),
            rule_repo=RuleRepository(engine),
            file_identity_repo=file_identity_repo,
            track_repo=track_repo,
            album_repo=AlbumRepository(engine),
            artist_repo=ArtistRepository(engine),
            database_writer=database_writer,
            job_queue=job_queue,
            scanner_worker=scanner_worker,
            hash_worker=hash_worker,
            fingerprint_worker=fingerprint_worker,
            dispatcher=dispatcher,
        )

    def close(self) -> None:
        """Release resources held by this container.

        Stops the dispatcher (waiting for any in-flight scan/hash work to
        finish) and the database writer thread (flushing anything still
        buffered) before disposing the database engine's connection pool.
        Call this during application shutdown; tests should call it (or
        use the ``container`` fixture, which does) to avoid leaking
        SQLite connections and background threads across test cases.
        """
        self.dispatcher.stop()
        self.database_writer.stop()
        self.engine.dispose()

"""Unit tests for RuleWorker."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Engine

from musicvault.core.event_bus import EventBus
from musicvault.db.repositories.artist_repo import ArtistRepository
from musicvault.db.repositories.job_repo import JobRepository
from musicvault.db.repositories.review_repo import ReviewRepository
from musicvault.db.repositories.rule_repo import RuleRepository
from musicvault.db.repositories.track_repo import TrackRepository
from musicvault.db.uuid_utils import generate_uuid7
from musicvault.models.entities.job import Job, JobStatus, JobType
from musicvault.models.entities.review_item import ReviewStatus, ReviewType
from musicvault.models.entities.track import LibraryZone, Track
from musicvault.services.job_queue_service import JobQueueService
from musicvault.services.review_queue_service import ReviewQueueService
from musicvault.services.rules_engine import RulesEngine
from musicvault.workers.io.rule_worker import RuleWorker

_NOW = datetime(2026, 7, 16, tzinfo=UTC)


def _make_track(library_id: UUID, track_id: UUID, **overrides: object) -> Track:
    defaults: dict[str, object] = {
        "id": track_id,
        "library_id": library_id,
        "zone": LibraryZone.INCOMING,
        "file_path": "C:/incoming/low.mp3",
        "file_name": "low.mp3",
        "file_size": 1024,
        "file_modified": _NOW,
        "created_at": _NOW,
        "updated_at": _NOW,
        "codec": "mp3",
        "bitrate": 96,
    }
    defaults.update(overrides)
    return Track(**defaults)  # type: ignore[arg-type]


def test_execute_seeds_defaults_and_flags_low_bitrate(
    track_repo: TrackRepository,
    job_queue: JobQueueService,
    job_repo: JobRepository,
    review_repo: ReviewRepository,
    rule_repo: RuleRepository,
    engine: Engine,
    library_id: UUID,
    track_id: UUID,
) -> None:
    track_repo.upsert(_make_track(library_id, track_id))
    event_bus = EventBus()
    rules = RulesEngine(
        rule_repo,
        track_repo,
        ArtistRepository(engine),
        ReviewQueueService(review_repo, track_repo, event_bus),
        event_bus,
    )
    job_id = job_queue.enqueue(
        JobType.EVALUATE_RULES, library_id, {"track_id": str(track_id)}, now=_NOW
    )
    job_repo.update_status(job_id, JobStatus.RUNNING)

    RuleWorker(track_repo, rules, job_queue).execute(
        Job(
            id=job_id,
            library_id=library_id,
            job_type=JobType.EVALUATE_RULES,
            status=JobStatus.RUNNING,
            payload={"track_id": str(track_id)},
            created_at=_NOW,
        )
    )

    assert job_repo.get(job_id).status is JobStatus.COMPLETED  # type: ignore[union-attr]
    assert len(rule_repo.list_by_library(library_id)) == 3
    pending = review_repo.list_by_status(ReviewStatus.PENDING, library_id=library_id)
    assert any(item.review_type is ReviewType.LOW_QUALITY for item in pending)


def test_execute_marks_failed_when_track_missing(
    track_repo: TrackRepository,
    job_queue: JobQueueService,
    job_repo: JobRepository,
    review_repo: ReviewRepository,
    rule_repo: RuleRepository,
    engine: Engine,
    library_id: UUID,
) -> None:
    missing = generate_uuid7()
    event_bus = EventBus()
    rules = RulesEngine(
        rule_repo,
        track_repo,
        ArtistRepository(engine),
        ReviewQueueService(review_repo, track_repo, event_bus),
        event_bus,
    )
    job_id = job_queue.enqueue(
        JobType.EVALUATE_RULES, library_id, {"track_id": str(missing)}, now=_NOW
    )
    job_repo.update_status(job_id, JobStatus.RUNNING)

    RuleWorker(track_repo, rules, job_queue).execute(
        Job(
            id=job_id,
            library_id=library_id,
            job_type=JobType.EVALUATE_RULES,
            status=JobStatus.RUNNING,
            payload={"track_id": str(missing)},
            created_at=_NOW,
        )
    )

    status = job_repo.get(job_id)
    assert status is not None
    assert status.status is JobStatus.RETRY
    assert status.error_message is not None
    assert "not found" in status.error_message

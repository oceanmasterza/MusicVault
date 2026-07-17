"""DuplicateWorker — runs `detect_duplicates` jobs through DuplicateMatcher.

I/O / DB-bound (Tier 2). Finds other tracks in the library sharing an
exact matching key (content hash > Chromaprint hash > MusicBrainz
recording ID), persists a duplicate group with quality-ranked members,
creates a ``possible_duplicate`` review item linked to the group, then
chains to `evaluate_rules` — so the rules engine sees the real
``has_lossless_duplicate`` flag (docs/architecture/10-revision-v2.md:
"Rules evaluate after metadata identification and duplicate detection").

Also the first writer of ``tracks.quality_score``: every track that
joins a group gets scored and persisted.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from musicvault.db.repositories.duplicate_repo import DuplicateRepository
from musicvault.db.repositories.file_identity_repo import FileIdentityRepository
from musicvault.db.repositories.track_repo import TrackRepository
from musicvault.db.uuid_utils import generate_uuid7
from musicvault.models.entities.duplicate_group import MatchType
from musicvault.models.entities.job import Job, JobType
from musicvault.models.entities.review_item import ReviewType
from musicvault.models.entities.track import Track
from musicvault.models.services.duplicate_matcher import DuplicateMatcher
from musicvault.services.dto.review_dto import ReviewItemCreate
from musicvault.services.job_queue_service import JobQueueService
from musicvault.services.review_queue_service import ReviewQueueService

# Tier order: identical bytes beat identical audio beat same recording.
_TIER_ORDER = (MatchType.HASH, MatchType.FINGERPRINT, MatchType.MBID)


class DuplicateWorker:
    def __init__(
        self,
        track_repo: TrackRepository,
        file_identity_repo: FileIdentityRepository,
        duplicate_repo: DuplicateRepository,
        matcher: DuplicateMatcher,
        review_queue: ReviewQueueService,
        job_queue: JobQueueService,
    ) -> None:
        self._tracks = track_repo
        self._identities = file_identity_repo
        self._duplicates = duplicate_repo
        self._matcher = matcher
        self._reviews = review_queue
        self._job_queue = job_queue

    def execute(self, job: Job) -> None:
        track_id = UUID(job.payload["track_id"])
        track = self._tracks.get_by_id(track_id)
        if track is None:
            self._job_queue.mark_failed(job.id, f"Track {track_id} not found")
            return

        now = datetime.now(UTC)
        identity = self._identities.get(track_id)
        candidates = self._duplicates.find_matching_track_ids(
            job.library_id,
            track_id,
            content_hash=identity.content_hash_sha256 if identity else None,
            fingerprint_hash=identity.fingerprint_hash if identity else None,
            mb_recording_id=track.mb_recording_id,
        )

        match_type = next((tier for tier in _TIER_ORDER if tier in candidates), None)
        if match_type is not None:
            self._persist_group(job.library_id, track, candidates[match_type], match_type, now)

        self._job_queue.enqueue(
            JobType.EVALUATE_RULES,
            job.library_id,
            {"track_id": str(track_id)},
            parent_job_id=job.id,
            now=now,
        )
        self._job_queue.mark_completed(job.id)

    def _persist_group(
        self,
        library_id: UUID,
        track: Track,
        matched_ids: list[UUID],
        match_type: MatchType,
        now: datetime,
    ) -> None:
        members = [track] + [
            loaded
            for track_id in matched_ids
            if (loaded := self._tracks.get_by_id(track_id)) is not None
        ]
        if len(members) < 2:
            return

        scored = [self._ensure_quality_score(member, now) for member in members]

        existing = self._duplicates.find_open_group_for_track(track.id, match_type)
        group_id = existing.id if existing is not None else generate_uuid7()
        group, group_members = self._matcher.build_group(
            group_id, library_id, scored, match_type, detected_at=now
        )
        self._duplicates.save_group(group, group_members)

        best = next(member for member in group_members if member.is_best)
        self._reviews.create_item(
            ReviewItemCreate(
                library_id=library_id,
                review_type=ReviewType.POSSIBLE_DUPLICATE,
                title=f"{group.track_count} duplicate copies detected ({match_type.value})",
                track_id=track.id,
                duplicate_group_id=group.id,
                confidence=group.match_confidence,
                description=(
                    f"Matched by {match_type.value}; best copy has "
                    f"quality score {best.quality_score}"
                ),
                payload={
                    "group_id": str(group.id),
                    "match_type": match_type.value,
                    "best_track_id": str(group.best_track_id),
                    "track_ids": [str(member.track_id) for member in group_members],
                },
            ),
            now=now,
        )

    def _ensure_quality_score(self, track: Track, now: datetime) -> Track:
        score = self._matcher.score(track)
        if track.quality_score == score:
            return track
        updated = replace(track, quality_score=score, updated_at=now)
        self._tracks.upsert(updated)
        return updated

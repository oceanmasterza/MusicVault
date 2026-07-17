"""RuleWorker — runs `evaluate_rules` jobs through RulesEngine.

I/O / DB-bound (Tier 2). Seeds default rules on first evaluation for a
library, builds :class:`~musicvault.services.dto.rule_dto.RuleContext`
(including the real ``has_lossless_duplicate`` flag from Phase 9
duplicate groups), evaluates enabled rules, and applies safe actions
(flag review, set artist/genre). Zone moves are parked as review items
until Phase 10.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from musicvault.db.repositories.duplicate_repo import DuplicateRepository
from musicvault.db.repositories.track_repo import TrackRepository
from musicvault.models.entities.job import Job
from musicvault.services.job_queue_service import JobQueueService
from musicvault.services.rules_engine import RulesEngine


class RuleWorker:
    def __init__(
        self,
        track_repo: TrackRepository,
        rules_engine: RulesEngine,
        duplicate_repo: DuplicateRepository,
        job_queue: JobQueueService,
    ) -> None:
        self._tracks = track_repo
        self._rules = rules_engine
        self._duplicates = duplicate_repo
        self._job_queue = job_queue

    def execute(self, job: Job) -> None:
        track_id = UUID(job.payload["track_id"])
        track = self._tracks.get_by_id(track_id)
        if track is None:
            self._job_queue.mark_failed(job.id, f"Track {track_id} not found")
            return

        now = datetime.now(UTC)
        self._rules.ensure_defaults(job.library_id, now=now)
        context = self._rules.build_context(
            track,
            has_lossless_duplicate=self._duplicates.has_lossless_duplicate(track_id),
        )
        matches = self._rules.evaluate(track, context)
        self._rules.apply_matches(track, matches, now=now)
        self._job_queue.mark_completed(job.id)

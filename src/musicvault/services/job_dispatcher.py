"""JobDispatcher — polls the job queue and dispatches ready jobs to
worker pools.

Only `scan_directory` (I/O — `ThreadPoolExecutor`) and `hash_file`
(CPU — `ProcessPoolExecutor`) are wired up here: Phase 4's worker set.
Later phases add one route per new worker as it's built (see
docs/architecture/08-performance.md, "Three-Tier Worker Model") rather
than pre-registering pools for workers that don't exist yet.

Crash recovery (docs/architecture/10-revision-v2.md, "Resume After
Crash") is split into two steps by design:

1. :meth:`recover` — reset-orphaned-jobs. Callers must run this once,
   before :meth:`start`, on every application startup — a `running`
   job found then can only mean the previous process crashed or was
   killed mid-execution.
2. `promote_due_retries`, called every poll cycle inside :meth:`run_cycle`
   — moves jobs whose backoff has elapsed back to `pending` so
   :meth:`~musicvault.services.job_queue_service.JobQueueService.claim_pending`
   picks them up.
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from typing import Any

from loguru import logger

from musicvault.models.entities.job import Job, JobType
from musicvault.services.job_queue_service import JobQueueService
from musicvault.workers.cpu.hash_worker import HashWorker, compute_hash
from musicvault.workers.io.scanner_worker import ScannerWorker


class JobDispatcher:
    def __init__(
        self,
        job_queue: JobQueueService,
        scanner_worker: ScannerWorker,
        hash_worker: HashWorker,
        *,
        scanner_threads: int = 1,
        hash_processes: int | None = None,
        claim_batch_size: int = 10,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._job_queue = job_queue
        self._scanner_worker = scanner_worker
        self._hash_worker = hash_worker
        self._claim_batch_size = claim_batch_size
        self._poll_interval_seconds = poll_interval_seconds
        self._scan_pool = ThreadPoolExecutor(
            max_workers=scanner_threads, thread_name_prefix="musicvault-scan"
        )
        self._hash_pool = ProcessPoolExecutor(max_workers=hash_processes)
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None

    def recover(self) -> int:
        """Reset any jobs left `running` by a previous crash. Call once,
        before :meth:`start`."""
        return self._job_queue.recover_orphaned()

    def run_cycle(self) -> list[Future[Any]]:
        """Claim and dispatch one round of ready work.

        Returns the futures submitted this cycle — mainly so tests can
        wait on them deterministically instead of polling on a timer.
        Note that for `hash_file` futures, `.result()` completing does
        not guarantee :meth:`HashWorker.handle_result` has *also*
        finished running — see the done-callback caveat on
        :meth:`_handle_hash_result`.
        """
        self._job_queue.promote_due_retries()

        futures: list[Future[Any]] = []
        for job in self._job_queue.claim_pending(JobType.SCAN_DIRECTORY, self._claim_batch_size):
            futures.append(self._scan_pool.submit(self._run_scan, job))
        for job in self._job_queue.claim_pending(JobType.HASH_FILE, self._claim_batch_size):
            future = self._hash_pool.submit(compute_hash, job.payload)
            future.add_done_callback(self._make_hash_callback(job))
            futures.append(future)
        return futures

    def start(self) -> None:
        """Start polling in a background thread. Safe to call once per instance."""
        self._thread = threading.Thread(
            target=self._poll_loop, name="musicvault-dispatcher", daemon=True
        )
        self._thread.start()

    def stop(self, *, timeout: float | None = 10.0) -> None:
        """Stop polling and shut down both worker pools, waiting for any
        in-flight work to finish."""
        self._shutdown.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        self._scan_pool.shutdown(wait=True)
        self._hash_pool.shutdown(wait=True)

    def _poll_loop(self) -> None:
        while not self._shutdown.is_set():
            try:
                self.run_cycle()
            except Exception:
                logger.exception("JobDispatcher poll cycle failed")
            self._shutdown.wait(timeout=self._poll_interval_seconds)

    def _run_scan(self, job: Job) -> None:
        """Runs on a `_scan_pool` thread. Unlike the hash pipeline, this
        can call `JobQueueService` directly on failure — no process
        boundary, no done-callback race."""
        try:
            self._scanner_worker.execute(job)
        except Exception as exc:
            logger.exception("ScannerWorker crashed on job {}", job.id)
            self._job_queue.mark_failed(job.id, str(exc))

    def _make_hash_callback(self, job: Job) -> Any:
        def _on_done(future: Future[dict[str, Any]]) -> None:
            self._handle_hash_result(job, future)

        return _on_done

    def _handle_hash_result(self, job: Job, future: Future[dict[str, Any]]) -> None:
        """Runs on the `ProcessPoolExecutor`'s internal callback thread,
        once `compute_hash` returns — not on `_hash_pool`'s worker
        process itself, and not synchronously with whatever called
        `future.result()` elsewhere (`Future.set_result` notifies
        waiters *before* invoking done-callbacks, so `.result()`
        returning is not proof this method has run — see the CPython
        `concurrent.futures._base.Future.set_result` source)."""
        try:
            result = future.result()
            self._hash_worker.handle_result(job, result)
        except Exception as exc:
            logger.exception("Failed to handle hash_file result for job {}", job.id)
            self._job_queue.mark_failed(job.id, str(exc))

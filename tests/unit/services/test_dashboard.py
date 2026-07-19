"""Tests for dashboard snapshot assembly."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from musicvault.app import bootstrap
from musicvault.db.uuid_utils import generate_uuid7
from musicvault.models.entities.library import Library
from musicvault.models.entities.track import LibraryZone, Track
from musicvault.services.dashboard import PIPELINE_STAGES, build_dashboard_snapshot


def test_dashboard_empty_library_insight(tmp_path: Path) -> None:
    container = bootstrap(base_dir_override=tmp_path, console_logging=False)
    try:
        snap = build_dashboard_snapshot(container, None)
        assert snap.has_library is False
        assert "Settings" in snap.insight
    finally:
        container.close()


def test_dashboard_snapshot_with_tracks_and_confidence(tmp_path: Path) -> None:
    container = bootstrap(base_dir_override=tmp_path, console_logging=False)
    try:
        now = datetime.now(UTC)
        library_id = generate_uuid7()
        container.library_repo.upsert(
            Library(
                id=library_id,
                name="Dash Lib",
                incoming_path=str(tmp_path / "in"),
                staging_path=str(tmp_path / "st"),
                library_path=str(tmp_path / "lib"),
                archive_path=str(tmp_path / "ar"),
                created_at=now,
                updated_at=now,
            )
        )
        tracks = [
            Track(
                id=generate_uuid7(),
                library_id=library_id,
                zone=LibraryZone.STAGING,
                file_path=str(tmp_path / "a.flac"),
                file_name="a.flac",
                file_size=1,
                file_modified=now,
                created_at=now,
                updated_at=now,
                overall_confidence=0.95,
                needs_review=False,
            ),
            Track(
                id=generate_uuid7(),
                library_id=library_id,
                zone=LibraryZone.INCOMING,
                file_path=str(tmp_path / "b.flac"),
                file_name="b.flac",
                file_size=1,
                file_modified=now,
                created_at=now,
                updated_at=now,
                overall_confidence=0.70,
                needs_review=True,
            ),
            Track(
                id=generate_uuid7(),
                library_id=library_id,
                zone=LibraryZone.LIBRARY,
                file_path=str(tmp_path / "c.flac"),
                file_name="c.flac",
                file_size=1,
                file_modified=now,
                created_at=now,
                updated_at=now,
                overall_confidence=None,
                needs_review=False,
            ),
        ]
        container.track_repo.upsert_batch(tracks)

        snap = build_dashboard_snapshot(container, library_id)
        assert snap.has_library is True
        assert snap.library_name == "Dash Lib"
        assert snap.track_count == 3
        assert snap.confidence["high"] == 1
        assert snap.confidence["fair"] == 1
        assert snap.confidence["unscored"] == 1
        assert snap.confidence["flagged"] == 1
        assert len(snap.stages) == len(PIPELINE_STAGES)
        assert snap.tracks_by_zone[LibraryZone.STAGING.value] == 1
        assert snap.insight
    finally:
        container.close()

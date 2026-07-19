"""Library browse page — tracks by zone."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from musicvault.core.container import Container
from musicvault.gui.widgets.desktop import copy_text_to_clipboard, open_path, reveal_in_explorer
from musicvault.models.entities.job import JobType
from musicvault.models.entities.track import LibraryZone


class LibraryPage(QWidget):
    """Lists tracks for the selected library, filtered by zone tab."""

    def __init__(self, container: Container, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._library_id: UUID | None = None
        self._file_paths: list[str] = []

        layout = QVBoxLayout(self)
        heading = QLabel("Library")
        heading.setProperty("heading", True)
        layout.addWidget(heading)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Zone:"))
        self._zone = QComboBox()
        self._zone.addItem("All zones", None)
        for zone in LibraryZone:
            self._zone.addItem(zone.value.title(), zone)
        self._zone.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(self._zone)
        toolbar.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by title or file name…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self.refresh)
        toolbar.addWidget(self._search, stretch=1)
        scan_btn = QPushButton("Scan incoming")
        scan_btn.setProperty("secondary", True)
        scan_btn.setToolTip("Enqueue a scan of this library’s Incoming folder.")
        scan_btn.clicked.connect(self._scan_incoming)
        toolbar.addWidget(scan_btn)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Title", "Zone", "File", "Confidence", "Quality"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        self._table.doubleClicked.connect(self._reveal_selected)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        self._counts = QLabel("")
        layout.addWidget(self._counts)

        reveal = QAction("Reveal in Explorer", self)
        reveal.setShortcut(QKeySequence("Ctrl+Return"))
        reveal.triggered.connect(self._reveal_selected)
        self.addAction(reveal)

    def set_library(self, library_id: UUID | None) -> None:
        self._library_id = library_id
        self.refresh()

    def refresh(self) -> None:
        self._table.setRowCount(0)
        self._file_paths = []
        if self._library_id is None:
            self._counts.setText("No library selected — create one in Settings.")
            return

        zone = self._zone.currentData()
        needle = self._search.text().strip().lower()
        tracks = self._container.track_repo.get_by_library(self._library_id, zone=zone, limit=500)
        if needle:
            tracks = [
                track
                for track in tracks
                if needle in (track.title or "").lower()
                or needle in (track.file_name or "").lower()
                or needle in (track.file_path or "").lower()
            ]
        self._table.setRowCount(len(tracks))
        for row, track in enumerate(tracks):
            self._file_paths.append(track.file_path)
            self._table.setItem(row, 0, QTableWidgetItem(track.title or "(untitled)"))
            self._table.setItem(row, 1, QTableWidgetItem(track.zone.value))
            self._table.setItem(row, 2, QTableWidgetItem(track.file_name or track.file_path))
            conf = (
                f"{track.overall_confidence:.0%}" if track.overall_confidence is not None else "—"
            )
            self._table.setItem(row, 3, QTableWidgetItem(conf))
            quality = str(track.quality_score) if track.quality_score is not None else "—"
            item = QTableWidgetItem(quality)
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._table.setItem(row, 4, item)

        counts = self._container.track_repo.count_by_zone(self._library_id)
        parts = [f"{name}: {count}" for name, count in sorted(counts.items())]
        self._counts.setText(f"{len(tracks)} shown · " + (" · ".join(parts) if parts else "empty"))

    def _selected_path(self) -> str | None:
        rows = {index.row() for index in self._table.selectedIndexes()}
        if len(rows) != 1:
            return None
        row = next(iter(rows))
        if 0 <= row < len(self._file_paths):
            return self._file_paths[row]
        return None

    def _context_menu(self, pos: object) -> None:
        path = self._selected_path()
        if not path:
            return
        menu = QMenu(self)
        reveal = menu.addAction("Reveal in Explorer")
        copy = menu.addAction("Copy path")
        open_parent = menu.addAction("Open containing folder")
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))  # type: ignore[arg-type]
        if chosen is reveal:
            reveal_in_explorer(path)
        elif chosen is copy:
            copy_text_to_clipboard(path)
        elif chosen is open_parent:
            open_path(Path(path).parent)

    def _reveal_selected(self, *_args: object) -> None:
        path = self._selected_path()
        if path:
            reveal_in_explorer(path)

    def _scan_incoming(self) -> None:
        if self._library_id is None:
            QMessageBox.warning(self, "Library", "Select or create a library in Settings first.")
            return
        library = self._container.library_repo.get(self._library_id)
        if library is None:
            return
        stats = self._container.job_queue.get_stats(library.id)
        if stats.by_type.get(JobType.SCAN_DIRECTORY.value, 0) > 0:
            QMessageBox.information(self, "Library", "A scan is already queued for this library.")
            return
        self._container.job_queue.enqueue(
            JobType.SCAN_DIRECTORY,
            library.id,
            {
                "directory": library.incoming_path,
                "zone": LibraryZone.INCOMING.value,
            },
        )
        QMessageBox.information(self, "Library", f"Scan queued for:\n{library.incoming_path}")

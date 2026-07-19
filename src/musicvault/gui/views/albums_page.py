"""Albums browse page — DB albums linked to this library."""

from __future__ import annotations

from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from musicvault.core.container import Container
from musicvault.gui.widgets.browse import fill_track_table
from musicvault.gui.widgets.desktop import reveal_in_explorer


class AlbumsPage(QWidget):
    """List albums for the active library; selecting one shows tracks."""

    def __init__(self, container: Container, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._container = container
        self._library_id: UUID | None = None
        self._filter_artist_id: UUID | None = None
        self._album_ids: list[UUID] = []
        self._track_paths: list[str] = []

        layout = QVBoxLayout(self)
        heading = QLabel("Albums")
        heading.setProperty("heading", True)
        layout.addWidget(heading)
        help_lbl = QLabel(
            "Albums created during Identify. Select a row to list its tracks."
        )
        help_lbl.setWordWrap(True)
        help_lbl.setProperty("muted", True)
        layout.addWidget(help_lbl)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Search:"))
        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter by album or artist…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self.refresh)
        toolbar.addWidget(self._search, stretch=1)
        self._filter_label = QLabel("")
        self._filter_label.setProperty("muted", True)
        toolbar.addWidget(self._filter_label)
        self._clear_filter = QPushButton("Clear filter")
        self._clear_filter.setProperty("secondary", True)
        self._clear_filter.setVisible(False)
        self._clear_filter.clicked.connect(lambda: self.set_artist_filter(None))
        toolbar.addWidget(self._clear_filter)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Album", "Artist", "Year", "Tracks", "Cover"]
        )
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._on_album_selected)
        splitter.addWidget(self._table)

        tracks_box = QWidget()
        tracks_layout = QVBoxLayout(tracks_box)
        tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_label = QLabel("Select an album to list tracks")
        self._tracks_label.setProperty("muted", True)
        tracks_layout.addWidget(self._tracks_label)
        self._tracks = QTableWidget(0, 4)
        self._tracks.setHorizontalHeaderLabels(["Title", "Zone", "File", "Confidence"])
        self._tracks.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._tracks.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._tracks.horizontalHeader().setStretchLastSection(True)
        self._tracks.doubleClicked.connect(self._reveal_track)
        tracks_layout.addWidget(self._tracks)
        splitter.addWidget(tracks_box)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter)

        self._status = QLabel("")
        layout.addWidget(self._status)

    def set_library(self, library_id: UUID | None) -> None:
        self._library_id = library_id
        self.refresh()

    def set_artist_filter(self, artist_id: UUID | None) -> None:
        self._filter_artist_id = artist_id
        if artist_id is None:
            self._filter_label.setText("")
            self._clear_filter.setVisible(False)
        else:
            artist = self._container.artist_repo.get(artist_id)
            name = artist.name if artist else str(artist_id)
            self._filter_label.setText(f"Filtered: {name}")
            self._clear_filter.setVisible(True)
        self.refresh()

    def refresh(self) -> None:
        self._table.setRowCount(0)
        self._album_ids = []
        self._tracks.setRowCount(0)
        self._track_paths = []
        self._tracks_label.setText("Select an album to list tracks")
        if self._library_id is None:
            self._status.setText("No library selected — create one in Settings.")
            return
        needle = self._search.text().strip() or None
        rows = self._container.album_repo.list_for_library(
            self._library_id,
            artist_id=self._filter_artist_id,
            query=needle,
            limit=500,
        )
        self._table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self._album_ids.append(row.album_id)
            self._table.setItem(i, 0, QTableWidgetItem(row.title))
            self._table.setItem(i, 1, QTableWidgetItem(row.artist_name or "—"))
            self._table.setItem(i, 2, QTableWidgetItem(str(row.year) if row.year else "—"))
            self._table.setItem(i, 3, QTableWidgetItem(str(row.track_count)))
            self._table.setItem(i, 4, QTableWidgetItem("Yes" if row.has_cover else "Missing"))
        self._status.setText(f"{len(rows)} album(s)")

    def _selected_album_id(self) -> UUID | None:
        rows = {index.row() for index in self._table.selectedIndexes()}
        if len(rows) != 1:
            return None
        row = next(iter(rows))
        if 0 <= row < len(self._album_ids):
            return self._album_ids[row]
        return None

    def _on_album_selected(self) -> None:
        album_id = self._selected_album_id()
        if album_id is None or self._library_id is None:
            return
        tracks = self._container.track_repo.list_by_album(
            self._library_id, album_id, limit=500
        )
        album = self._container.album_repo.get(album_id)
        title = album.title if album else "Album"
        self._tracks_label.setText(f"Tracks on {title} ({len(tracks)})")
        self._track_paths = fill_track_table(
            self._tracks, tracks, columns=("Title", "Zone", "File", "Confidence")
        )

    def _reveal_track(self) -> None:
        rows = {index.row() for index in self._tracks.selectedIndexes()}
        if len(rows) != 1:
            return
        row = next(iter(rows))
        if 0 <= row < len(self._track_paths):
            reveal_in_explorer(self._track_paths[row])

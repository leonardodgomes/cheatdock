"""Setup screen: pick which cheat sheets become tabs, and in which order."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .loader import Sheet

CATEGORY_ORDER = ["Shell & OS", "Data", "Programming", "Tools"]


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Tile(QFrame):
    """One cheat sheet in the library. Click anywhere on it to tick / untick."""

    toggled = Signal(str, bool)

    def __init__(self, sheet: Sheet, checked: bool):
        super().__init__()
        self.sheet = sheet
        self.setObjectName("tile")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 11)
        lay.setSpacing(4)
        top = QHBoxLayout()
        self.box = QCheckBox(sheet.name)
        self.box.setObjectName("tileName")
        self.box.setChecked(checked)
        self.box.toggled.connect(self._changed)
        count = QLabel(f"{sheet.count} commands")
        count.setObjectName("tileCount")
        top.addWidget(self.box)
        top.addStretch(1)
        top.addWidget(count)
        lay.addLayout(top)
        if sheet.description:
            desc = QLabel(sheet.description)
            desc.setObjectName("tileDesc")
            desc.setWordWrap(True)
            lay.addWidget(desc)
        lay.addStretch(1)
        self.setProperty("checked", checked)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.box.toggle()
        super().mouseReleaseEvent(event)

    def _changed(self, on: bool) -> None:
        self.setProperty("checked", on)
        _repolish(self)
        self.toggled.emit(self.sheet.id, on)


class SetupDialog(QDialog):
    def __init__(self, sheets: list[Sheet], enabled: list[str], style: str, first_run: bool = False):
        super().__init__(None, Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setObjectName("setup")
        self.setWindowTitle("CheatDock setup")
        self.setStyleSheet(style)
        self.resize(940, 640)
        self.sheets = {s.id: s for s in sheets}

        main = QVBoxLayout(self)
        main.setContentsMargins(22, 18, 22, 16)
        main.setSpacing(10)

        title = QLabel("Welcome to CheatDock 👋" if first_run else "Choose your cheat sheets")
        title.setObjectName("setupTitle")
        main.addWidget(title)
        sub = QLabel(
            "Tick the cheat sheets you use. Each one becomes a tab in the panel. "
            "Drag them in the list on the right to change the tab order. "
            "You can come back here any time with the ⚙ button."
        )
        sub.setObjectName("note")
        sub.setWordWrap(True)
        main.addWidget(sub)

        body = QHBoxLayout()
        body.setSpacing(16)
        main.addLayout(body, 1)

        # Left: library of tiles grouped by category.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lib = QWidget()
        lib.setObjectName("tabBody")
        lib_lay = QVBoxLayout(lib)
        lib_lay.setContentsMargins(0, 0, 8, 0)
        lib_lay.setSpacing(6)
        self.tiles: dict[str, Tile] = {}

        cats: dict[str, list[Sheet]] = {}
        for s in sheets:
            cats.setdefault(s.category, []).append(s)
        ordered = [c for c in CATEGORY_ORDER if c in cats] + sorted(c for c in cats if c not in CATEGORY_ORDER)
        for cat in ordered:
            header = QLabel(cat.upper())
            header.setObjectName("section")
            lib_lay.addWidget(header)
            grid = QGridLayout()
            grid.setSpacing(8)
            for i, sheet in enumerate(sorted(cats[cat], key=lambda s: s.name.lower())):
                tile = Tile(sheet, sheet.id in enabled)
                tile.toggled.connect(self._on_toggled)
                self.tiles[sheet.id] = tile
                grid.addWidget(tile, i // 2, i % 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            lib_lay.addLayout(grid)
        lib_lay.addStretch(1)
        scroll.setWidget(lib)
        body.addWidget(scroll, 3)

        # Right: tab order.
        right = QVBoxLayout()
        order_title = QLabel("TAB ORDER")
        order_title.setObjectName("section")
        right.addWidget(order_title)
        fav = QLabel("★ Favorites is always the first tab")
        fav.setObjectName("note")
        right.addWidget(fav)
        self.order = QListWidget()
        self.order.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.order.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.order.setToolTip("Drag to reorder")
        for sid in enabled:
            if sid in self.sheets:
                self._add_to_order(sid)
        right.addWidget(self.order, 1)
        hint = QLabel("Drag to reorder ↕")
        hint.setObjectName("note")
        right.addWidget(hint)
        body.addLayout(right, 1)

        # Bottom buttons.
        bottom = QHBoxLayout()
        all_btn = QPushButton("Select all")
        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn = QPushButton("Clear")
        none_btn.clicked.connect(lambda: self._set_all(False))
        self.count_lbl = QLabel()
        self.count_lbl.setObjectName("note")
        cancel = QPushButton("Skip for now" if first_run else "Cancel")
        cancel.clicked.connect(self.reject)
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("primary")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.accept)
        for w in (all_btn, none_btn):
            bottom.addWidget(w)
        bottom.addSpacing(10)
        bottom.addWidget(self.count_lbl)
        bottom.addStretch(1)
        bottom.addWidget(cancel)
        bottom.addWidget(self.save_btn)
        main.addLayout(bottom)
        self._update_count()

    def _add_to_order(self, sid: str) -> None:
        item = QListWidgetItem(f"⋮⋮  {self.sheets[sid].name}")
        item.setData(Qt.ItemDataRole.UserRole, sid)
        self.order.addItem(item)

    def _on_toggled(self, sid: str, on: bool) -> None:
        ids = self.selected_ids()
        if on and sid not in ids:
            self._add_to_order(sid)
        elif not on:
            for i in range(self.order.count()):
                if self.order.item(i).data(Qt.ItemDataRole.UserRole) == sid:
                    self.order.takeItem(i)
                    break
        self._update_count()

    def _set_all(self, on: bool) -> None:
        for tile in self.tiles.values():
            tile.box.setChecked(on)

    def _update_count(self) -> None:
        n = self.order.count()
        self.count_lbl.setText(f"{n} selected")
        self.save_btn.setEnabled(n > 0)

    def selected_ids(self) -> list[str]:
        return [self.order.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.order.count())]

"""CheatDock - a cheat sheet panel docked to the edge of the screen."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import (
    QDir, QEasingCurve, QFileSystemWatcher, QLockFile, QPoint, QPropertyAnimation,
    QRect, QRectF, QStandardPaths, Qt, QTimer, QUrl, Signal,
)
from PySide6.QtGui import (
    QAction, QColor, QCursor, QDesktopServices, QFont, QFontDatabase, QGuiApplication,
    QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
    QScrollArea, QSystemTrayIcon, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from . import __version__
from .hotkey import GlobalHotkey
from .loader import Config, Item, Sheet, base_dir, load_config, load_sheets
from .setup import SetupDialog

ACCENT = "#4f9dff"  # tray / taskbar icon colour

# Colour palettes for the two themes. Every colour in the UI comes from here.
THEMES = {
    "dark": {
        "bg": "#1b1d22", "border": "#2c2f37", "text": "#d7dae0", "strong": "#ffffff",
        "muted": "#8b919c", "input": "#262930", "input_border": "#343842",
        "btn": "#aeb3bd", "btn_hover": "#2a2d35", "accent": "#4f9dff", "on_accent": "#0d1117",
        "scroll": "#3a3e48", "scroll_hover": "#4a4f5b",
        "card": "#23262d", "card_hover": "#2a2e37", "card_hover_border": "#3c4250",
        "copied": "#1f3a2a", "copied_border": "#3fb96f",
        "code": "#e8c07d", "error": "#ff7b72",
    },
    "light": {
        "bg": "#f6f7f9", "border": "#d9dce3", "text": "#24292f", "strong": "#0d1117",
        "muted": "#6a737d", "input": "#ffffff", "input_border": "#cfd4dc",
        "btn": "#57606a", "btn_hover": "#e6e9ee", "accent": "#0969da", "on_accent": "#ffffff",
        "scroll": "#c4c9d2", "scroll_hover": "#aab0bb",
        "card": "#ffffff", "card_hover": "#f0f4fa", "card_hover_border": "#bfcde0",
        "copied": "#e3f6ea", "copied_border": "#2da44e",
        "code": "#9a4d00", "error": "#cf222e",
    },
}


def check_mark(color: str) -> str:
    """Draw a small check-mark PNG for checkboxes and return its path for the stylesheet."""
    import tempfile

    path = Path(tempfile.gettempdir()) / f"cheatdock_check_{color.strip('#')}_v2.png"
    if not path.exists():
        pix = QPixmap(30, 30)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color), 4.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPolyline([QPoint(7, 16), QPoint(13, 22), QPoint(24, 9)])
        p.end()
        pix.save(str(path), "PNG")
    return path.as_posix()


def build_style(t: dict) -> str:
    return f"""
#panel {{ background: {t['bg']}; border-left: 1px solid {t['border']}; border-right: 1px solid {t['border']}; }}
QWidget {{ color: {t['text']}; font-family: "Segoe UI", sans-serif; font-size: 10pt; }}
#appTitle {{ font-size: 12pt; font-weight: 600; color: {t['strong']}; }}
QLineEdit {{
    background: {t['input']}; border: 1px solid {t['input_border']}; border-radius: 6px;
    padding: 7px 10px; selection-background-color: {t['accent']}; selection-color: {t['on_accent']};
}}
QLineEdit:focus {{ border-color: {t['accent']}; }}
QToolButton {{
    background: transparent; border: 1px solid transparent; border-radius: 5px;
    padding: 3px 8px; color: {t['btn']};
}}
QToolButton:hover {{ background: {t['btn_hover']}; color: {t['strong']}; }}
QToolButton:checked {{ background: {t['accent']}; color: {t['on_accent']}; }}
#themeBtn {{ font-family: "Segoe UI Symbol", "Segoe UI"; font-size: 12pt; padding: 0px 7px; }}
#hideBtn {{ font-size: 12pt; font-weight: 700; padding: 0px 8px; }}
#closeBtn:hover {{ background: #e5534b; color: #ffffff; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: {t['muted']}; padding: 7px 10px;
    border-bottom: 2px solid transparent; margin-right: 2px;
}}
QTabBar::tab:selected {{ color: {t['strong']}; border-bottom-color: {t['accent']}; }}
QTabBar::tab:hover {{ color: {t['strong']}; }}
QScrollArea, #tabBody {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['scroll']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {t['scroll_hover']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
#section {{
    color: {t['accent']}; font-size: 8.5pt; font-weight: 700; letter-spacing: 1px;
    padding: 12px 2px 4px 2px;
}}
#card {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 7px; }}
#card:hover {{ background: {t['card_hover']}; border-color: {t['card_hover_border']}; }}
#card[copied="true"] {{ background: {t['copied']}; border-color: {t['copied_border']}; }}
#cardTitle {{ color: {t['strong']}; font-weight: 600; }}
#code {{
    color: {t['code']}; background: transparent;
    font-family: "Cascadia Mono", "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: 9.5pt;
}}
#note {{ color: {t['muted']}; font-size: 9pt; }}
#status {{ color: {t['muted']}; font-size: 8.5pt; padding: 4px 2px; }}
#status[error="true"] {{ color: {t['error']}; }}
#empty {{ color: {t['muted']}; padding: 30px; }}
#star {{ background: transparent; border: none; padding: 0px 2px; font-size: 13pt; color: {t['muted']}; }}
#star:hover {{ background: transparent; color: #e3a008; }}
#star:checked {{ background: transparent; color: #e3a008; }}
#source {{ color: {t['accent']}; font-size: 8.5pt; }}
#hint {{ color: {t['muted']}; padding: 24px 10px; font-size: 9.5pt; }}
#gearBtn {{ font-family: "Segoe UI Symbol", "Segoe UI"; font-size: 12pt; padding: 0px 7px; }}
QDialog#setup {{ background: {t['bg']}; }}
#setupTitle {{ font-size: 16pt; font-weight: 600; color: {t['strong']}; }}
#tile {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 8px; }}
#tile:hover {{ border-color: {t['card_hover_border']}; }}
#tile[checked="true"] {{ background: {t['card_hover']}; border: 1px solid {t['accent']}; }}
#tileName {{ font-weight: 600; color: {t['strong']}; spacing: 8px; }}
#tileDesc, #tileCount {{ color: {t['muted']}; font-size: 9pt; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border: 1px solid {t['input_border']};
    border-radius: 4px; background: {t['input']};
}}
QCheckBox::indicator:checked {{
    background: {t['accent']}; border-color: {t['accent']}; image: url({check_mark(t['on_accent'])});
}}
QListWidget {{
    background: {t['input']}; border: 1px solid {t['input_border']}; border-radius: 6px;
    padding: 4px; outline: 0;
}}
QListWidget::item {{ padding: 7px 8px; border-radius: 5px; color: {t['text']}; }}
QListWidget::item:hover {{ background: {t['btn_hover']}; }}
QListWidget::item:selected {{ background: {t['accent']}; color: {t['on_accent']}; }}
QPushButton {{
    background: {t['card']}; color: {t['text']}; border: 1px solid {t['input_border']};
    border-radius: 6px; padding: 7px 16px;
}}
QPushButton:hover {{ border-color: {t['accent']}; }}
QPushButton#primary {{ background: {t['accent']}; color: {t['on_accent']}; border-color: {t['accent']}; font-weight: 600; }}
QPushButton:disabled {{ color: {t['muted']}; background: {t['btn_hover']}; border-color: {t['border']}; }}
QToolTip {{ color: {t['text']}; background: {t['card']}; border: 1px solid {t['border']}; padding: 4px; }}
"""


def mono_font() -> QFont:
    families = set(QFontDatabase.families())
    for name in ("Cascadia Mono", "Cascadia Code", "JetBrains Mono", "Consolas", "Menlo"):
        if name in families:
            font = QFont(name)
            break
    else:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSizeF(9.5)
    return font


def app_icon() -> QIcon:
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(ACCENT))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(4, 4, 56, 56, 12, 12)
    p.setPen(QColor("#0d1117"))
    font = QFont("Consolas", 22)
    font.setBold(True)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, ">_")
    p.end()
    return QIcon(pix)


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Card(QFrame):
    """One command. Click to copy its code, click the star to add it to Favorites."""

    clicked = Signal(object)
    star_toggled = Signal(object, bool)

    def __init__(self, item: Item, font: QFont, starred: bool = False, show_source: bool = False):
        super().__init__()
        self.item = item
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to copy")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(11, 7, 7, 9)
        lay.setSpacing(4)

        head = QHBoxLayout()
        head.setSpacing(4)
        title = QLabel(item.title)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        head.addWidget(title, 1)
        self.star = QToolButton()
        self.star.setObjectName("star")
        self.star.setCheckable(True)
        self.star.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_starred(starred)
        self.star.toggled.connect(self._on_star)
        head.addWidget(self.star, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(head)

        if show_source:
            src = QLabel(f"{item.sheet_name} · {item.section}")
            src.setObjectName("source")
            lay.addWidget(src)

        code = QLabel(item.code)
        code.setObjectName("code")
        code.setFont(font)
        code.setTextFormat(Qt.TextFormat.PlainText)
        code.setWordWrap(True)
        lay.addWidget(code)

        if item.note:
            note = QLabel(item.note)
            note.setObjectName("note")
            note.setWordWrap(True)
            lay.addWidget(note)

        self.haystack = " ".join(
            [item.title, item.code, item.note, item.section, item.sheet_name]
        ).lower()

    def set_starred(self, on: bool) -> None:
        self.star.blockSignals(True)
        self.star.setChecked(on)
        self.star.blockSignals(False)
        self.star.setText("★" if on else "☆")
        self.star.setToolTip("Remove from Favorites" if on else "Add to Favorites")

    def _on_star(self, on: bool) -> None:
        self.set_starred(on)
        self.star_toggled.emit(self, on)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self)
        super().mouseReleaseEvent(event)

    def flash(self) -> None:
        self.setProperty("copied", True)
        repolish(self)
        QTimer.singleShot(700, self._unflash)

    def _unflash(self) -> None:
        self.setProperty("copied", False)
        repolish(self)


class SheetTab(QScrollArea):
    """Scrollable list of sections and cards (one cheat sheet, or Favorites)."""

    def __init__(self, title: str, sections: list[tuple[str, list[Item]]], dock: "Dock",
                 show_source: bool = False, hint: str = ""):
        super().__init__()
        self.title = title
        self.hint = hint
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("tabBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(2, 0, 8, 12)
        lay.setSpacing(6)

        self.groups: list[tuple[QLabel, list[Card]]] = []
        for name, items in sections:
            if not items:
                continue
            header = QLabel(name.upper())
            header.setObjectName("section")
            lay.addWidget(header)
            cards = []
            for item in items:
                card = dock.make_card(item, show_source)
                lay.addWidget(card)
                cards.append(card)
            self.groups.append((header, cards))

        self.empty = QLabel()
        self.empty.setObjectName("hint" if hint else "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.hide()
        lay.addWidget(self.empty)
        lay.addStretch(1)
        self.setWidget(body)
        self.apply_filter([])

    def cards(self) -> list[Card]:
        return [c for _, cards in self.groups for c in cards]

    def apply_filter(self, terms: list[str]) -> int:
        total = 0
        for header, cards in self.groups:
            shown = 0
            for card in cards:
                ok = all(t in card.haystack for t in terms)
                card.setVisible(ok)
                shown += ok
            header.setVisible(shown > 0)
            total += shown
        self.empty.setText(self.hint if (self.hint and not terms) else "No matches in this tab")
        self.empty.setVisible(total == 0)
        if terms:
            self.verticalScrollBar().setValue(0)
        return total

    def first_visible(self) -> Card | None:
        for card in self.cards():
            if card.isVisibleTo(self):
                return card
        return None


class DragArea(QWidget):
    """A widget that moves the dock when dragged and reports plain clicks."""

    clicked = Signal()

    def __init__(self, dock: "Dock", parent=None):
        super().__init__(parent)
        self.dock = dock
        self._press: QPoint | None = None
        self._dragging = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._dragging = False
            self.dock.hover_timer.stop()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._press is not None:
            pos = event.globalPosition().toPoint()
            if not self._dragging and (pos - self._press).manhattanLength() > 6:
                self._dragging = True
                self.dock.drag_start(self._press)
            if self._dragging:
                self.dock.drag_move(pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press is not None:
            if self._dragging:
                self.dock.drag_end(event.globalPosition().toPoint())
            else:
                self.clicked.emit()
        self._press = None
        self._dragging = False
        super().mouseReleaseEvent(event)


class EdgeIcon(DragArea):
    """Small tab on the screen edge shown while the panel is closed."""

    def __init__(self, dock: "Dock", parent=None):
        super().__init__(dock, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("CheatDock: hover or click to open, drag to move (even to another screen)")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Extend the shape past the screen edge so only the inner corners are rounded.
        ext = 12
        if self.dock.edge == "right":
            shape = QRectF(1, 1, w + ext, h - 2)
        else:
            shape = QRectF(-ext, 1, w + ext - 1, h - 2)
        t = self.dock.colors
        p.setBrush(QColor(t["card_hover"] if self.underMouse() else t["bg"]))
        p.setPen(QPen(QColor(t["accent"]), 1.6))
        p.drawRoundedRect(shape, 10, 10)
        font = QFont("Consolas")
        font.setPixelSize(max(10, int(h * 0.36)))
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(t["accent"]))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, ">_")
        p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


def state_file() -> Path:
    folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation))
    return folder / "state.json"


class Dock(QWidget):
    def __init__(self, cfg: Config):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.cfg = cfg
        self.expanded = False      # where we are heading (open / closed)
        self.mode = "icon"         # what is drawn right now: "icon" or "panel"
        self.pinned = False
        self.dragging = False
        self._drag_offset = QPoint()
        self.mono = mono_font()
        self.tabs_by_sheet: list[SheetTab] = []
        self.all_sheets: list[Sheet] = []
        self.items_by_key: dict[str, Item] = {}
        self.cards_by_key: dict[str, list[Card]] = {}

        # Personal choices, saved in state.json.
        self.enabled: list[str] | None = None   # None = setup never done
        self.favorites: list[str] = []
        self.usage: dict[str, int] = {}
        self._fav_dirty = False

        # Position: which screen, which side, and how far down the icon sits.
        self.screen_name = ""
        self.edge = cfg.edge
        self.y_frac = min(1.0, max(0.0, float(cfg.icon_position)))
        self.theme = self._default_theme()
        self._load_state()

        self.setWindowTitle("CheatDock")
        self.setWindowIcon(app_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(float(cfg.opacity))

        self.icon = EdgeIcon(self, self)
        self.icon.clicked.connect(lambda: self.expand(focus=True))

        self.panel = QFrame(self)
        self.panel.setObjectName("panel")
        self._build_panel()
        self.set_theme(self.theme, save=False)

        self.anim = QPropertyAnimation(self, b"geometry", self)
        self.anim.setDuration(170)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.finished.connect(self._on_anim_done)

        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda _: self._apply_position())
        app.screenRemoved.connect(lambda _: QTimer.singleShot(200, self._apply_position))

        self.hover_timer = QTimer(self, singleShot=True, interval=int(cfg.hover_delay_ms))
        self.hover_timer.timeout.connect(self.expand)
        self.collapse_timer = QTimer(self, singleShot=True, interval=int(cfg.collapse_delay_ms))
        self.collapse_timer.timeout.connect(self._maybe_collapse)

        # Reload automatically when a cheat sheet file changes.
        self.watcher = QFileSystemWatcher(self)
        self.save_timer = QTimer(self, singleShot=True, interval=1500)
        self.save_timer.timeout.connect(self._save_state)
        self.reload_timer = QTimer(self, singleShot=True, interval=300)
        self.reload_timer.timeout.connect(self.reload)
        self.watcher.directoryChanged.connect(lambda _: self.reload_timer.start())
        self.watcher.fileChanged.connect(lambda _: self.reload_timer.start())

        self.reload()
        self._apply_position()

    # ---------- UI ----------
    def _build_panel(self) -> None:
        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(14, 12, 10, 8)
        lay.setSpacing(8)

        # The title bar doubles as a drag handle to move the panel.
        title_bar = DragArea(self)
        title_bar.setCursor(Qt.CursorShape.SizeAllCursor)
        title_bar.setToolTip("Drag to move to another side or screen")
        top = QHBoxLayout(title_bar)
        top.setContentsMargins(0, 0, 0, 0)
        title = QLabel("CheatDock")
        title.setObjectName("appTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top.addWidget(title)
        top.addStretch(1)

        gear_btn = QToolButton(text="⚙")
        gear_btn.setObjectName("gearBtn")
        gear_btn.setToolTip("Choose cheat sheets (Ctrl+,)")
        gear_btn.clicked.connect(lambda: self.open_setup())
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self.open_setup())
        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("themeBtn")
        self.theme_btn.clicked.connect(self.toggle_theme)
        self.pin_btn = QToolButton(text="Pin", checkable=True)
        self.pin_btn.setToolTip("Keep the panel open (Ctrl+P)")
        self.pin_btn.toggled.connect(self.set_pinned)
        reload_btn = QToolButton(text="Reload")
        reload_btn.setToolTip("Reload cheat sheets (F5)")
        reload_btn.clicked.connect(self.reload)
        hide_btn = QToolButton(text="–")
        hide_btn.setObjectName("hideBtn")
        hide_btn.setToolTip("Hide to the edge icon (Esc)")
        hide_btn.clicked.connect(lambda: self.collapse(force=True))
        close_btn = QToolButton(text="✕")
        close_btn.setObjectName("closeBtn")
        close_btn.setToolTip("Close CheatDock (Ctrl+Q)")
        close_btn.clicked.connect(QApplication.quit)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=QApplication.quit)
        for b in (gear_btn, self.theme_btn, self.pin_btn, reload_btn, hide_btn, close_btn):
            top.addWidget(b)
        lay.addWidget(title_bar)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search all commands…   (Enter copies the first match)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        self.search.returnPressed.connect(self.copy_first_match)
        lay.addWidget(self.search)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setUsesScrollButtons(True)
        self.tabs.tabBar().setDrawBase(False)
        lay.addWidget(self.tabs, 1)

        self.status = QLabel()
        self.status.setObjectName("status")
        lay.addWidget(self.status)
        self._idle_status()

        QShortcut(QKeySequence("Esc"), self, activated=self._on_escape)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.focus_search)
        QShortcut(QKeySequence("F5"), self, activated=self.reload)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.pin_btn.toggle)
        QShortcut(QKeySequence("Ctrl+T"), self, activated=self.toggle_theme)
        for i in range(9):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self,
                      activated=lambda i=i: self.tabs.setCurrentIndex(min(i, self.tabs.count() - 1)))

    def _idle_status(self) -> None:
        hk = self.cfg.hotkey.upper() if self.cfg.hotkey else "—"
        self._set_status(f"Click to copy · {hk} toggles · Ctrl+T theme · Esc hides")

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setProperty("error", error)
        repolish(self.status)

    # ---------- cheat sheets, favorites, usage ----------
    def make_card(self, item: Item, show_source: bool = False) -> Card:
        card = Card(item, self.mono, item.key in self.favorites, show_source)
        card.clicked.connect(self.copy_card)
        card.star_toggled.connect(self.on_star)
        self.cards_by_key.setdefault(item.key, []).append(card)
        return card

    def _forget_cards(self, tab: SheetTab) -> None:
        for card in tab.cards():
            lst = self.cards_by_key.get(card.item.key, [])
            if card in lst:
                lst.remove(card)

    def active_ids(self) -> list[str]:
        known = {s.id for s in self.all_sheets}
        if self.enabled is None:
            return [s.id for s in self.all_sheets if s.default] or [s.id for s in self.all_sheets[:4]]
        return [sid for sid in self.enabled if sid in known]

    def _favorites_tab(self) -> SheetTab:
        favs = [self.items_by_key[k] for k in self.favorites if k in self.items_by_key]
        top = sorted(
            (k for k, n in self.usage.items() if n >= 2 and k in self.items_by_key),
            key=lambda k: -self.usage[k],
        )[:10]
        used = [self.items_by_key[k] for k in top]
        hint = ("No favorites yet.\n\nClick ☆ on any command to keep it here.\n"
                "Commands you copy often also show up here under Most used.")
        return SheetTab("★ Favorites", [("Favorites", favs), ("Most used", used)],
                        self, show_source=True, hint=hint)

    def refresh_favorites(self) -> None:
        if not self.tabs_by_sheet:
            return
        current = self.tabs.currentIndex()
        old = self.tabs_by_sheet[0]
        self._forget_cards(old)
        new = self._favorites_tab()
        self.tabs_by_sheet[0] = new
        self.tabs.removeTab(0)
        self.tabs.insertTab(0, new, new.title)
        old.deleteLater()
        self.tabs.setCurrentIndex(max(0, current))
        self._fav_dirty = False
        self.apply_filter(self.search.text())

    def on_star(self, card: Card, on: bool) -> None:
        key = card.item.key
        if on and key not in self.favorites:
            self.favorites.append(key)
        elif not on and key in self.favorites:
            self.favorites.remove(key)
        for other in self.cards_by_key.get(key, []):
            other.set_starred(on)
        self._save_state()
        self._set_status(("Added to" if on else "Removed from") + f" Favorites: {card.item.title}")
        QTimer.singleShot(2500, self._idle_status)
        # Rebuild after this click finishes (the clicked card may be deleted).
        QTimer.singleShot(0, self.refresh_favorites)

    def open_setup(self, first_run: bool = False) -> None:
        self.collapse_timer.stop()
        was_pinned = self.pinned
        self.pinned = True  # keep the panel from closing behind the dialog
        enabled = self.active_ids() if not first_run else [s.id for s in self.all_sheets if s.default]
        dlg = SetupDialog(self.all_sheets, enabled, build_style(self.colors), first_run)
        area = self._screen().availableGeometry()
        dlg.move(area.center() - dlg.rect().center())
        ok = dlg.exec() == SetupDialog.DialogCode.Accepted
        self.pinned = was_pinned
        if ok:
            self.enabled = dlg.selected_ids()
        elif self.enabled is None:
            self.enabled = enabled  # "Skip for now" keeps the defaults
        else:
            return
        self._save_state()
        self.reload()
        self._set_status(f"{len(self.active_ids())} cheat sheets enabled · ⚙ to change")
        QTimer.singleShot(3000, self._idle_status)

    def reload(self) -> None:
        current = self.tabs_by_sheet[self.tabs.currentIndex()].title if self.tabs_by_sheet else ""
        sheets, errors = load_sheets()
        self.all_sheets = sheets
        self.items_by_key = {it.key: it for sh in sheets for it in sh.items}
        by_id = {sh.id: sh for sh in sheets}

        self.tabs.clear()
        for tab in self.tabs_by_sheet:
            tab.deleteLater()
        self.tabs_by_sheet = []
        self.cards_by_key = {}

        tabs = [self._favorites_tab()]
        for sid in self.active_ids():
            sheet = by_id[sid]
            tabs.append(SheetTab(sheet.name, [(sec.name, sec.items) for sec in sheet.sections], self))
        for tab in tabs:
            self.tabs_by_sheet.append(tab)
            self.tabs.addTab(tab, tab.title)
        start = 1 if len(tabs) > 1 else 0
        titles = [t.title for t in tabs]
        self.tabs.setCurrentIndex(titles.index(current) if current in titles else start)
        self._fav_dirty = False

        folder = base_dir() / "cheatsheets"
        if self.watcher.files():
            self.watcher.removePaths(self.watcher.files())
        if folder.exists():
            if str(folder) not in self.watcher.directories():
                self.watcher.addPath(str(folder))
            files = [str(f) for f in folder.glob("*.y*ml")]
            if files:
                self.watcher.addPaths(files)

        self.apply_filter(self.search.text())
        if errors:
            self._set_status("YAML error → " + " | ".join(errors), error=True)
        elif not sheets:
            self._set_status(f"No cheat sheets found in {folder}", error=True)
        else:
            self._idle_status()

    def apply_filter(self, text: str) -> None:
        terms = text.lower().split()
        counts = []
        for i, tab in enumerate(self.tabs_by_sheet):
            n = tab.apply_filter(terms)
            counts.append(n)
            self.tabs.setTabText(i, f"{tab.title} ({n})" if terms else tab.title)
        # Jump to a tab that has results if the current one has none.
        idx = self.tabs.currentIndex()
        if terms and 0 <= idx < len(counts) and counts[idx] == 0:
            for i, n in enumerate(counts):
                if n:
                    self.tabs.setCurrentIndex(i)
                    break

    def copy_card(self, card: Card) -> None:
        QGuiApplication.clipboard().setText(card.item.code)
        card.flash()
        key = card.item.key
        self.usage[key] = self.usage.get(key, 0) + 1
        self._fav_dirty = True  # "Most used" is refreshed when the panel closes
        self.save_timer.start()
        self._set_status(f"Copied: {card.item.title}")
        QTimer.singleShot(2500, self._idle_status)

    def copy_first_match(self) -> None:
        tab = self.tabs.currentWidget()
        if isinstance(tab, SheetTab):
            card = tab.first_visible()
            if card:
                self.copy_card(card)

    def focus_search(self) -> None:
        self.search.setFocus()
        self.search.selectAll()

    def _on_escape(self) -> None:
        if self.search.text():
            self.search.clear()
        else:
            self.collapse(force=True)

    # ---------- theme ----------
    def _default_theme(self) -> str:
        choice = str(self.cfg.theme).lower()
        if choice in THEMES:
            return choice
        # "system": follow the Windows light/dark setting
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
            return "light" if scheme == Qt.ColorScheme.Light else "dark"
        except AttributeError:
            return "dark"

    @property
    def colors(self) -> dict:
        return THEMES[self.theme]

    def set_theme(self, theme: str, save: bool = True) -> None:
        self.theme = theme if theme in THEMES else "dark"
        self.setStyleSheet(build_style(self.colors))
        light = self.theme == "light"
        self.theme_btn.setText("☾" if light else "☀")  # moon / sun
        self.theme_btn.setToolTip(
            ("Switch to dark theme" if light else "Switch to light theme") + " (Ctrl+T)"
        )
        self.icon.update()
        if save:
            self._save_state()

    def toggle_theme(self) -> None:
        self.set_theme("light" if self.theme == "dark" else "dark")

    # ---------- position / state ----------
    def _screen(self):
        for s in QGuiApplication.screens():
            if s.name() == self.screen_name:
                return s
        return QGuiApplication.primaryScreen()

    def _load_state(self) -> None:
        try:
            data = json.loads(state_file().read_text(encoding="utf-8"))
            self.screen_name = str(data.get("screen", ""))
            if data.get("edge") in ("left", "right"):
                self.edge = data["edge"]
            self.y_frac = min(1.0, max(0.0, float(data.get("y", self.y_frac))))
            if data.get("theme") in THEMES:
                self.theme = data["theme"]
            if isinstance(data.get("enabled"), list):
                self.enabled = [str(x) for x in data["enabled"]]
            if isinstance(data.get("favorites"), list):
                self.favorites = [str(x) for x in data["favorites"]]
            if isinstance(data.get("usage"), dict):
                self.usage = {str(k): int(v) for k, v in data["usage"].items()}
        except (OSError, ValueError, TypeError):
            pass

    def _save_state(self) -> None:
        try:
            path = state_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {"screen": self.screen_name, "edge": self.edge,
                    "y": round(self.y_frac, 4), "theme": self.theme,
                    "enabled": self.enabled, "favorites": self.favorites, "usage": self.usage}
            path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        except OSError:
            pass

    def _target_rect(self, mode: str) -> QRect:
        """Geometry for 'icon', 'panel' or 'strip' (1px wide, used to slide in/out)."""
        area = self._screen().availableGeometry()
        if mode == "icon":
            size = int(self.cfg.icon_size)
            w, h = size, size
            y = area.top() + round(self.y_frac * max(0, area.height() - size))
        else:
            w = int(self.cfg.width) if mode == "panel" else 1
            h, y = area.height(), area.top()
        x = area.left() if self.edge == "left" else area.right() + 1 - w
        return QRect(x, y, w, h)

    def _apply_position(self) -> None:
        self.anim.stop()
        self.setGeometry(self._target_rect(self.mode))
        self._layout_children()
        self.icon.update()

    def move_to_next_screen(self) -> None:
        screens = QGuiApplication.screens()
        if len(screens) < 2:
            return
        idx = screens.index(self._screen()) if self._screen() in screens else 0
        self.screen_name = screens[(idx + 1) % len(screens)].name()
        self._save_state()
        self._apply_position()

    # ---------- dragging (icon or title bar) ----------
    def drag_start(self, global_pos: QPoint) -> None:
        self.dragging = True
        self.anim.stop()
        self.hover_timer.stop()
        self.collapse_timer.stop()
        self._drag_offset = global_pos - self.pos()
        if self.mode == "panel":
            # Shrink the panel to a floating card while it is carried around.
            g = self.geometry()
            self.setGeometry(g.x(), g.y(), g.width(), min(g.height(), 420))
            self._layout_children()

    def drag_move(self, global_pos: QPoint) -> None:
        self.move(global_pos - self._drag_offset)

    def drag_end(self, global_pos: QPoint) -> None:
        screen = QGuiApplication.screenAt(global_pos) or self._screen()
        area = screen.availableGeometry()
        self.screen_name = screen.name()
        self.edge = "left" if global_pos.x() < area.center().x() else "right"
        if self.mode == "icon":
            size = int(self.cfg.icon_size)
            span = max(1, area.height() - size)
            self.y_frac = min(1.0, max(0.0, (self.y() - area.top()) / span))
        self._save_state()
        self.dragging = False
        self.icon.update()
        self.anim.stop()
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(self._target_rect(self.mode))
        self.anim.start()

    # ---------- open / close ----------
    def _layout_children(self) -> None:
        w, h = self.width(), self.height()
        if self.mode == "icon":
            self.panel.hide()
            self.icon.setGeometry(0, 0, w, h)
            self.icon.show()
        else:
            self.icon.hide()
            pw = int(self.cfg.width)
            # Anchor the panel to the moving side so it slides in from the edge.
            x = w - pw if self.edge == "left" else 0
            self.panel.setGeometry(x, 0, pw, h)
            self.panel.show()

    def resizeEvent(self, event):
        self._layout_children()
        super().resizeEvent(event)

    def _on_anim_done(self) -> None:
        if not self.expanded and self.mode == "panel" and not self.dragging:
            if self._fav_dirty:
                self.refresh_favorites()
            self.mode = "icon"
            self.setGeometry(self._target_rect("icon"))
            self._layout_children()

    def expand(self, focus: bool = False) -> None:
        self.collapse_timer.stop()
        self.hover_timer.stop()
        if not self.expanded and not self.dragging:
            self.expanded = True
            self.anim.stop()
            self.mode = "panel"
            self.setGeometry(self._target_rect("strip"))
            self._layout_children()
            self.anim.setStartValue(self.geometry())
            self.anim.setEndValue(self._target_rect("panel"))
            self.anim.start()
        self.raise_()
        if focus:
            self.activateWindow()
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
            self.focus_search()

    def collapse(self, force: bool = False) -> None:
        if not self.expanded or self.dragging or (self.pinned and not force):
            return
        if force and self.pinned:
            self.pin_btn.setChecked(False)
        self.expanded = False
        self.anim.stop()
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(self._target_rect("strip"))
        self.anim.start()

    def toggle(self) -> None:
        if self.expanded:
            self.collapse(force=True)
        else:
            self.expand(focus=True)

    def set_pinned(self, pinned: bool) -> None:
        self.pinned = pinned
        if pinned:
            self.expand()

    def _cursor_inside(self) -> bool:
        return self.geometry().contains(QCursor.pos())

    def _maybe_collapse(self) -> None:
        if not self._cursor_inside() and QApplication.activePopupWidget() is None:
            self.collapse()

    def enterEvent(self, event):
        self.collapse_timer.stop()
        if self.cfg.expand_on_hover and not self.expanded and not self.dragging:
            self.hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        if self.expanded and not self.pinned and not self.dragging:
            self.collapse_timer.start()
        super().leaveEvent(event)

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange and not self.isActiveWindow():
            if self.expanded and not self.pinned and not self.dragging and not self._cursor_inside():
                self.collapse_timer.start()
        super().changeEvent(event)


def build_tray(app: QApplication, dock: Dock) -> QSystemTrayIcon:
    tray = QSystemTrayIcon(app_icon(), app)
    tray.setToolTip(f"CheatDock {__version__} — {dock.cfg.hotkey}")
    menu = QMenu()

    def add(text, slot):
        act = QAction(text, menu)
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    add("Show / hide", dock.toggle)
    add("Choose cheat sheets…", lambda: dock.open_setup())
    add("Move to next screen", dock.move_to_next_screen)
    add("Light / dark theme", dock.toggle_theme)
    add("Reload cheat sheets", dock.reload)
    add("Open cheat sheets folder",
        lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(base_dir() / "cheatsheets"))))
    add("Edit config.yaml",
        lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(base_dir() / "config.yaml"))))
    menu.addSeparator()
    add("Quit", app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: dock.toggle() if reason == QSystemTrayIcon.ActivationReason.Trigger else None
    )
    tray.show()
    return tray


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("CheatDock")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())

    lock = QLockFile(QDir.tempPath() + "/cheatdock.lock")
    if not lock.tryLock(100):
        QMessageBox.information(None, "CheatDock", "CheatDock is already running (see the system tray).")
        return 0

    cfg = load_config()
    dock = Dock(cfg)
    dock.show()
    tray = build_tray(app, dock)  # noqa: F841 - keep a reference
    if dock.enabled is None:
        QTimer.singleShot(500, lambda: dock.open_setup(first_run=True))

    hotkey = None
    if cfg.hotkey:
        hotkey = GlobalHotkey(cfg.hotkey)
        hotkey.pressed.connect(dock.toggle)
        hotkey.failed.connect(lambda msg: dock._set_status(msg, error=True))
        hotkey.start()
        app.aboutToQuit.connect(hotkey.stop)

    app.aboutToQuit.connect(dock._save_state)
    code = app.exec()
    lock.unlock()
    return code

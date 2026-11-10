"""CheatDock - a cheat sheet panel docked to the edge of the screen."""

from __future__ import annotations

import sys

from PySide6.QtCore import (
    QDir, QEasingCurve, QFileSystemWatcher, QLockFile, QPropertyAnimation,
    QRect, Qt, QTimer, QUrl, Signal,
)
from PySide6.QtGui import (
    QAction, QColor, QCursor, QDesktopServices, QFont, QFontDatabase, QGuiApplication,
    QIcon, QKeySequence, QPainter, QPixmap, QShortcut,
)
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
    QScrollArea, QSystemTrayIcon, QTabWidget, QToolButton, QVBoxLayout, QWidget,
)

from . import __version__
from .hotkey import GlobalHotkey
from .loader import Config, Item, Sheet, base_dir, load_config, load_sheets

ACCENT = "#4f9dff"

STYLE = f"""
#panel {{ background: #1b1d22; border-left: 1px solid #2c2f37; border-right: 1px solid #2c2f37; }}
QWidget {{ color: #d7dae0; font-family: "Segoe UI", sans-serif; font-size: 10pt; }}
#appTitle {{ font-size: 12pt; font-weight: 600; color: #ffffff; }}
QLineEdit {{
    background: #262930; border: 1px solid #343842; border-radius: 6px;
    padding: 7px 10px; selection-background-color: {ACCENT};
}}
QLineEdit:focus {{ border-color: {ACCENT}; }}
QToolButton {{
    background: transparent; border: 1px solid transparent; border-radius: 5px;
    padding: 3px 8px; color: #aeb3bd;
}}
QToolButton:hover {{ background: #2a2d35; color: #ffffff; }}
QToolButton:checked {{ background: {ACCENT}; color: #0d1117; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: #8b919c; padding: 7px 10px;
    border-bottom: 2px solid transparent; margin-right: 2px;
}}
QTabBar::tab:selected {{ color: #ffffff; border-bottom-color: {ACCENT}; }}
QTabBar::tab:hover {{ color: #ffffff; }}
QScrollArea, #tabBody {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3a3e48; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #4a4f5b; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
#section {{
    color: {ACCENT}; font-size: 8.5pt; font-weight: 700; letter-spacing: 1px;
    padding: 12px 2px 4px 2px;
}}
#card {{ background: #23262d; border: 1px solid #2c2f37; border-radius: 7px; }}
#card:hover {{ background: #2a2e37; border-color: #3c4250; }}
#card[copied="true"] {{ background: #1f3a2a; border-color: #3fb96f; }}
#cardTitle {{ color: #ffffff; font-weight: 600; }}
#code {{
    color: #e8c07d; background: transparent;
    font-family: "Cascadia Mono", "Cascadia Code", "JetBrains Mono", "Consolas", monospace;
    font-size: 9.5pt;
}}
#note {{ color: #8b919c; font-size: 9pt; }}
#status {{ color: #8b919c; font-size: 8.5pt; padding: 4px 2px; }}
#status[error="true"] {{ color: #ff7b72; }}
#empty {{ color: #8b919c; padding: 30px; }}
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
    """One command. Click to copy its code."""

    clicked = Signal(object)

    def __init__(self, item: Item, section: str, font: QFont):
        super().__init__()
        self.item = item
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to copy")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(11, 8, 11, 9)
        lay.setSpacing(4)

        title = QLabel(item.title)
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        lay.addWidget(title)

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

        self.haystack = " ".join([item.title, item.code, item.note, section]).lower()

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
    """Scrollable list of the sections and cards of one cheat sheet."""

    def __init__(self, sheet: Sheet, font: QFont, on_click):
        super().__init__()
        self.sheet = sheet
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setObjectName("tabBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(2, 0, 8, 12)
        lay.setSpacing(6)

        self.groups: list[tuple[QLabel, list[Card]]] = []
        for section in sheet.sections:
            header = QLabel(section.name.upper())
            header.setObjectName("section")
            lay.addWidget(header)
            cards = []
            for item in section.items:
                card = Card(item, section.name, font)
                card.clicked.connect(on_click)
                lay.addWidget(card)
                cards.append(card)
            self.groups.append((header, cards))

        self.empty = QLabel("No matches in this tab")
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()
        lay.addWidget(self.empty)
        lay.addStretch(1)
        self.setWidget(body)

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
        self.empty.setVisible(total == 0)
        if terms:
            self.verticalScrollBar().setValue(0)
        return total

    def first_visible(self) -> Card | None:
        for _, cards in self.groups:
            for card in cards:
                if card.isVisibleTo(self):
                    return card
        return None


class Dock(QWidget):
    def __init__(self, cfg: Config):
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool,
        )
        self.cfg = cfg
        self.expanded = False
        self.pinned = False
        self.mono = mono_font()
        self.tabs_by_sheet: list[SheetTab] = []

        self.setWindowTitle("CheatDock")
        self.setWindowIcon(app_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(float(cfg.opacity))
        self.setStyleSheet(STYLE)

        # Thin strip that stays on screen while collapsed.
        self.handle = QFrame(self)
        self.handle.setStyleSheet(
            f"background: rgba(79,157,255,110); border-radius: {max(1, cfg.handle_width // 2)}px;"
        )
        self.handle.setCursor(Qt.CursorShape.PointingHandCursor)

        self.panel = QFrame(self)
        self.panel.setObjectName("panel")
        self._build_panel()

        self.anim = QPropertyAnimation(self, b"geometry", self)
        self.anim.setDuration(170)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.hover_timer = QTimer(self, singleShot=True, interval=140)
        self.hover_timer.timeout.connect(self.expand)
        self.collapse_timer = QTimer(self, singleShot=True, interval=int(cfg.collapse_delay_ms))
        self.collapse_timer.timeout.connect(self._maybe_collapse)

        # Reload automatically when a cheat sheet file changes.
        self.watcher = QFileSystemWatcher(self)
        self.reload_timer = QTimer(self, singleShot=True, interval=300)
        self.reload_timer.timeout.connect(self.reload)
        self.watcher.directoryChanged.connect(lambda _: self.reload_timer.start())
        self.watcher.fileChanged.connect(lambda _: self.reload_timer.start())

        self.reload()
        self.setGeometry(self._target_rect(False))

    # ---------- UI ----------
    def _build_panel(self) -> None:
        lay = QVBoxLayout(self.panel)
        lay.setContentsMargins(14, 12, 10, 8)
        lay.setSpacing(8)

        top = QHBoxLayout()
        title = QLabel("CheatDock")
        title.setObjectName("appTitle")
        top.addWidget(title)
        top.addStretch(1)

        self.pin_btn = QToolButton(text="Pin", checkable=True)
        self.pin_btn.setToolTip("Keep the panel open (Ctrl+P)")
        self.pin_btn.toggled.connect(self.set_pinned)
        reload_btn = QToolButton(text="Reload")
        reload_btn.setToolTip("Reload cheat sheets (F5)")
        reload_btn.clicked.connect(self.reload)
        close_btn = QToolButton(text="✕")
        close_btn.setToolTip("Hide (Esc)")
        close_btn.clicked.connect(lambda: self.collapse(force=True))
        for b in (self.pin_btn, reload_btn, close_btn):
            top.addWidget(b)
        lay.addLayout(top)

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
        for i in range(9):
            QShortcut(QKeySequence(f"Ctrl+{i + 1}"), self,
                      activated=lambda i=i: self.tabs.setCurrentIndex(min(i, self.tabs.count() - 1)))

    def _idle_status(self) -> None:
        hk = self.cfg.hotkey.upper() if self.cfg.hotkey else "—"
        self._set_status(f"Click to copy · {hk} toggles · Ctrl+1..9 tabs · Esc hides")

    def _set_status(self, text: str, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setProperty("error", error)
        repolish(self.status)

    def reload(self) -> None:
        current = self.tabs.tabText(self.tabs.currentIndex()).split(" (")[0] if self.tabs.count() else ""
        sheets, errors = load_sheets()

        self.tabs.clear()
        for tab in self.tabs_by_sheet:
            tab.deleteLater()
        self.tabs_by_sheet = []
        for sheet in sheets:
            tab = SheetTab(sheet, self.mono, self.copy_card)
            self.tabs_by_sheet.append(tab)
            self.tabs.addTab(tab, sheet.name)
            if sheet.name == current:
                self.tabs.setCurrentWidget(tab)

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
            self.tabs.setTabText(i, f"{tab.sheet.name} ({n})" if terms else tab.sheet.name)
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

    # ---------- docking / animation ----------
    def _target_rect(self, expanded: bool) -> QRect:
        area = QGuiApplication.primaryScreen().availableGeometry()
        hw, pw = int(self.cfg.handle_width), int(self.cfg.width)
        w = hw + pw if expanded else hw
        x = area.left() if self.cfg.edge == "left" else area.right() + 1 - w
        return QRect(x, area.top(), w, area.height())

    def resizeEvent(self, event):
        w, h = self.width(), self.height()
        hw, pw = int(self.cfg.handle_width), int(self.cfg.width)
        if self.cfg.edge == "left":
            self.panel.setGeometry(w - hw - pw, 0, pw, h)
            self.handle.setGeometry(w - hw, 0, hw, h)
        else:
            self.handle.setGeometry(0, 0, hw, h)
            self.panel.setGeometry(hw, 0, pw, h)
        super().resizeEvent(event)

    def _animate(self, expanded: bool) -> None:
        self.anim.stop()
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(self._target_rect(expanded))
        self.anim.start()

    def expand(self, focus: bool = False) -> None:
        self.collapse_timer.stop()
        if not self.expanded:
            self.expanded = True
            self._animate(True)
        self.raise_()
        if focus:
            self.activateWindow()
            if sys.platform == "win32":
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
            self.focus_search()

    def collapse(self, force: bool = False) -> None:
        if not self.expanded or (self.pinned and not force):
            return
        if force and self.pinned:
            self.pin_btn.setChecked(False)
        self.expanded = False
        self._animate(False)

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
        if self.cfg.expand_on_hover and not self.expanded:
            self.hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        if self.expanded and not self.pinned:
            self.collapse_timer.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        # Clicking the strip opens the panel even when hover is disabled.
        if not self.expanded:
            self.expand(focus=True)
        super().mousePressEvent(event)

    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange and not self.isActiveWindow():
            if self.expanded and not self.pinned and not self._cursor_inside():
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

    hotkey = None
    if cfg.hotkey:
        hotkey = GlobalHotkey(cfg.hotkey)
        hotkey.pressed.connect(dock.toggle)
        hotkey.failed.connect(lambda msg: dock._set_status(msg, error=True))
        hotkey.start()
        app.aboutToQuit.connect(hotkey.stop)

    code = app.exec()
    lock.unlock()
    return code

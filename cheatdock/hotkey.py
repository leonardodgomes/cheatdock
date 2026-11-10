"""System-wide hotkey for Windows using the Win32 RegisterHotKey API.

No extra dependency and no admin rights needed. On other platforms the
hotkey is simply disabled (the hover strip and tray icon still work).
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QThread, Signal

MODIFIERS = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002, "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012

NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE,
    ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC,
}


def parse_hotkey(text: str) -> tuple[int, int]:
    """'ctrl+alt+space' -> (modifiers, virtual key code). Raises ValueError."""
    mods, vk = 0, None
    for part in [p.strip().lower() for p in text.split("+") if p.strip()]:
        if part in MODIFIERS:
            mods |= MODIFIERS[part]
        elif part in NAMED_KEYS:
            vk = NAMED_KEYS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x70 + int(part[1:]) - 1
        else:
            raise ValueError(f"Unknown key '{part}' in hotkey '{text}'")
    if vk is None:
        raise ValueError(f"Hotkey '{text}' has no main key")
    return mods, vk


class GlobalHotkey(QThread):
    """Emits `pressed` whenever the hotkey is hit, from any application."""

    pressed = Signal()
    failed = Signal(str)

    def __init__(self, hotkey: str, parent=None):
        super().__init__(parent)
        self.hotkey = hotkey
        self._thread_id = 0

    def run(self) -> None:  # runs in the worker thread
        if sys.platform != "win32":
            self.failed.emit("Global hotkey is only supported on Windows.")
            return
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        try:
            mods, vk = parse_hotkey(self.hotkey)
        except ValueError as exc:
            self.failed.emit(str(exc))
            return

        self._thread_id = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, vk):
            self.failed.emit(
                f"Could not register hotkey '{self.hotkey}'. "
                "Another program may already use it - change it in config.yaml."
            )
            return

        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self.pressed.emit()
        finally:
            user32.UnregisterHotKey(None, 1)

    def stop(self) -> None:
        if sys.platform == "win32" and self._thread_id:
            import ctypes

            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self.wait(1000)

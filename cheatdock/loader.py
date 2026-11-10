"""Load the config file and the cheat sheet YAML files."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml


def base_dir() -> Path:
    """Folder that holds config.yaml and cheatsheets/.

    When frozen with PyInstaller this is the folder of the .exe, so users can
    edit the YAML files that sit next to it. Otherwise it is the repo root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


@dataclass
class Config:
    theme: str = "dark"            # starting theme: "dark", "light" or "system"
    edge: str = "right"            # starting side: "right" or "left"
    width: int = 440               # expanded width in px
    icon_size: int = 40            # size of the edge icon in px
    icon_position: float = 0.5     # starting height: 0 = top, 1 = bottom
    expand_on_hover: bool = True
    hover_delay_ms: int = 250
    collapse_delay_ms: int = 500
    hotkey: str = "ctrl+alt+space"
    opacity: float = 0.97


def load_config(path: Path | None = None) -> Config:
    path = path or base_dir() / "config.yaml"
    cfg = Config()
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key, value in data.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
    cfg.edge = "left" if str(cfg.edge).lower() == "left" else "right"
    return cfg


@dataclass
class Item:
    title: str
    code: str
    note: str = ""


@dataclass
class Section:
    name: str
    items: list[Item] = field(default_factory=list)


@dataclass
class Sheet:
    name: str
    order: int
    sections: list[Section] = field(default_factory=list)

    @property
    def count(self) -> int:
        return sum(len(s.items) for s in self.sections)


def load_sheets(folder: Path | None = None) -> tuple[list[Sheet], list[str]]:
    """Return (sheets, errors). A broken file is reported, not fatal."""
    folder = folder or base_dir() / "cheatsheets"
    sheets: list[Sheet] = []
    errors: list[str] = []
    for file in sorted(folder.glob("*.y*ml")):
        try:
            data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
            sheet = Sheet(
                name=str(data.get("name", file.stem)),
                order=int(data.get("order", 100)),
            )
            for sec in data.get("sections", []) or []:
                section = Section(name=str(sec.get("name", "")))
                for it in sec.get("items", []) or []:
                    section.items.append(
                        Item(
                            title=str(it.get("title", "")).strip(),
                            code=str(it.get("code", "")).rstrip("\n"),
                            note=str(it.get("note", "") or "").strip(),
                        )
                    )
                sheet.sections.append(section)
            sheets.append(sheet)
        except Exception as exc:  # noqa: BLE001 - show any parse error to the user
            errors.append(f"{file.name}: {exc}")
    sheets.sort(key=lambda s: (s.order, s.name.lower()))
    return sheets, errors

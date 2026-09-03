"""Format-agnostic data model shared by the HDF5 and LeRobot backends.

`Task` / `DemoRef` are lightweight metadata (populated by directory scanning);
`Episode` holds one demonstration's fully-loaded arrays, ready for display.
`scan_path()` / `load_episode()` auto-detect the on-disk format and dispatch
to the matching backend (`data_model.py` for raw LIBERO HDF5,
`lerobot_source.py` for LeRobot dataset directories).
"""

from __future__ import annotations

import dataclasses
from enum import Enum
from pathlib import Path

import numpy as np


class SourceKind(str, Enum):
    HDF5 = "hdf5"
    LEROBOT = "lerobot"


@dataclasses.dataclass
class DemoRef:
    """Lightweight reference to one demonstration/episode, no arrays loaded."""

    key: str
    num_steps: int


@dataclasses.dataclass
class Task:
    """Lightweight metadata about one task (a group of demonstrations sharing
    a language instruction), no arrays loaded."""

    kind: SourceKind
    display_name: str
    language_instruction: str
    fps: float
    demos: list[DemoRef]
    # Directory to remember as the starting point for "Open..." dialogs.
    source_root: Path
    # Opaque, backend-specific handle used by that backend's load_episode().
    backend_ref: object = None

    def __str__(self) -> str:
        return self.display_name


@dataclasses.dataclass
class Episode:
    """Fully loaded contents of one demonstration/episode."""

    key: str
    task: Task
    num_steps: int
    fps: float
    primary_label: str
    primary_rgb: np.ndarray
    wrist_label: str | None
    wrist_rgb: np.ndarray | None
    # Plottable signal name -> (array of shape (T,) or (T, D), per-dim labels).
    signals: dict[str, tuple[np.ndarray, list[str]]]


def scan_path(path: Path) -> list[Task]:
    """Scan a single HDF5 file, a directory of them, or a LeRobot dataset root."""
    from . import data_model, lerobot_source

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No such file or directory: {path}")
    if path.is_dir() and lerobot_source.is_lerobot_dataset(path):
        return lerobot_source.scan_dataset(path)
    return data_model.scan_path(path)


def load_episode(task: Task, demo_key: str) -> Episode:
    from . import data_model, lerobot_source

    if task.kind is SourceKind.LEROBOT:
        return lerobot_source.load_episode(task, demo_key)
    return data_model.load_episode(task, demo_key)

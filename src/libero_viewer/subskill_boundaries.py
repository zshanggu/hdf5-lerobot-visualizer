"""Optional overlay: per-demo sub-skill boundary annotations for raw LIBERO
HDF5 episodes, produced by zeyu_openpi's
`examples/libero/annotate_subskill_boundaries.py`.

That script writes one `subskill_boundaries.json` file (keyed by HDF5
filename, then by demo key) alongside a directory of task HDF5 files. This
module loads that file if present and looks up one demo's boundary list;
everything here is best-effort and additive -- a missing file, an unmatched
task/demo (including any LeRobot source, which this doesn't cover), or a
malformed JSON file all just mean "no overlay to show", never an error the
user has to deal with.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QColor

BOUNDARIES_FILENAME = "subskill_boundaries.json"

# Okabe-Ito colorblind-safe qualitative palette, one color per sub-skill
# index (1-based; cycles if a task ever has more than 4 sub-skills).
SKILL_COLORS = [QColor("#0072B2"), QColor("#E69F00"), QColor("#009E73"), QColor("#D55E00")]


def color_for_skill(skill_idx: int) -> QColor:
    return SKILL_COLORS[(skill_idx - 1) % len(SKILL_COLORS)]


def load_boundaries_file(directory: Path) -> dict | None:
    """Loads subskill_boundaries.json from `directory` if it exists there."""
    path = Path(directory) / BOUNDARIES_FILENAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"warning: failed to read {path}: {exc}")
        return None


def lookup(boundaries: dict | None, hdf5_filename: str, demo_key: str) -> list[dict] | None:
    """Returns the `boundaries` list (see the annotator script's docstring for
    the per-entry schema: skill_idx/prompt/start_frame/end_frame/
    detection_failed) for one demo, or None if this file/demo isn't covered.
    """
    if boundaries is None:
        return None
    task_entry = boundaries.get(hdf5_filename)
    if task_entry is None:
        return None
    demo_entry = task_entry.get("demos", {}).get(demo_key)
    if demo_entry is None:
        return None
    return demo_entry.get("boundaries")


def skill_at_frame(boundaries: list[dict] | None, frame_index: int) -> dict | None:
    """Returns the boundary entry whose [start_frame, end_frame] contains
    `frame_index`, or None (e.g. no boundaries loaded)."""
    if not boundaries:
        return None
    for b in boundaries:
        if b["start_frame"] <= frame_index <= b["end_frame"]:
            return b
    return None

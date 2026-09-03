"""Read-only access to raw LIBERO benchmark HDF5 demonstration files.

Each *_demo.hdf5 file corresponds to one task and contains a `data` group
with one subgroup per demonstration episode (`demo_0`, `demo_1`, ...).
"""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

from .sources import DemoRef, Episode, SourceKind, Task

# Signal display name -> (HDF5 dataset path relative to the demo group,
# per-dimension legend labels).
_SIGNAL_SPECS: list[tuple[str, str, list[str]]] = [
    ("Actions (7)", "actions", ["dx", "dy", "dz", "drx", "dry", "drz", "gripper"]),
    ("End-effector position (3)", "obs/ee_pos", ["x", "y", "z"]),
    ("End-effector orientation (3)", "obs/ee_ori", ["rx", "ry", "rz"]),
    ("Joint states (7)", "obs/joint_states", [f"j{i}" for i in range(1, 8)]),
    ("Gripper states (2)", "obs/gripper_states", ["left", "right"]),
    ("Reward", "rewards", ["reward"]),
]


def _safe_json(raw) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def scan_directory(directory: Path) -> list[Task]:
    """Scan a directory for LIBERO *.hdf5 files and read their metadata only.

    Only group/dataset attributes are touched here (cheap); no image or
    trajectory arrays are loaded, so scanning even large directories is fast.
    """
    directory = Path(directory)
    files = sorted(directory.glob("*.hdf5"))
    tasks: list[Task] = []
    for path in files:
        try:
            task = read_task_metadata(path)
        except (OSError, KeyError) as exc:
            print(f"warning: skipping {path.name}: {exc}")
            continue
        tasks.append(task)
    return tasks


def scan_path(path: Path) -> list[Task]:
    """Scan either a single *.hdf5 file or a directory of them.

    Raises FileNotFoundError if `path` doesn't exist, and ValueError if it's
    a file that isn't a readable LIBERO HDF5 task file.
    """
    path = Path(path)
    if path.is_dir():
        return scan_directory(path)
    if path.is_file():
        return [read_task_metadata(path)]
    raise FileNotFoundError(f"No such file or directory: {path}")


def read_task_metadata(path: Path) -> Task:
    path = Path(path)
    with h5py.File(path, "r") as f:
        data = f["data"]
        attrs = data.attrs

        env_args = _safe_json(attrs.get("env_args", "{}"))
        env_kwargs = env_args.get("env_kwargs", {})
        control_freq = float(env_kwargs.get("control_freq", 20))

        problem_info = _safe_json(attrs.get("problem_info", "{}"))
        language_instruction = problem_info.get("language_instruction", "")

        demo_keys = sorted(
            data.keys(), key=lambda k: int(k.split("_")[1]) if "_" in k else 0
        )
        demos = [
            DemoRef(key=k, num_steps=int(data[k]["actions"].shape[0]))
            for k in demo_keys
        ]

        return Task(
            kind=SourceKind.HDF5,
            display_name=path.stem,
            language_instruction=language_instruction,
            fps=control_freq,
            demos=demos,
            source_root=path.parent,
            backend_ref=path,
        )


def load_episode(task: Task, demo_key: str) -> Episode:
    """Fully load one demonstration's arrays (images + trajectories) into RAM."""
    path: Path = task.backend_ref
    with h5py.File(path, "r") as f:
        demo = f["data"][demo_key]
        num_steps = int(demo["actions"].shape[0])

        # LIBERO renders camera images with MuJoCo's OpenGL offscreen renderer,
        # whose row order is bottom-to-top, so frames need a vertical flip to
        # display right-side-up.
        agentview_rgb = np.ascontiguousarray(demo["obs"]["agentview_rgb"][()][:, ::-1])
        eye_in_hand_rgb = np.ascontiguousarray(demo["obs"]["eye_in_hand_rgb"][()][:, ::-1])

        signals: dict[str, tuple[np.ndarray, list[str]]] = {}
        for display_name, dataset_path, labels in _SIGNAL_SPECS:
            group, _, name = dataset_path.rpartition("/")
            source = demo[group] if group else demo
            if name not in source:
                continue
            arr = np.asarray(source[name][()])
            if arr.ndim == 1:
                arr = arr[:, None]
            signals[display_name] = (arr, labels)

        return Episode(
            key=demo_key,
            task=task,
            num_steps=num_steps,
            fps=task.fps,
            primary_label="agentview",
            primary_rgb=agentview_rgb,
            wrist_label="eye_in_hand",
            wrist_rgb=eye_in_hand_rgb,
            signals=signals,
        )

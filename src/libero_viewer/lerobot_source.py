"""Read-only access to LeRobot dataset directories (codebase_version v2.x).

A LeRobot dataset root looks like:

    meta/
      info.json          fps, feature schema, data_path/video_path templates
      tasks.jsonl         {task_index, task}
      episodes.jsonl       {episode_index, tasks: [str, ...], length}
    data/
      chunk-000/
        episode_000000.parquet   per-frame columns (incl. embedded image bytes
                                  when a feature's dtype is "image")
    videos/                       per-episode mp4s, one per camera, when a
      chunk-000/<video_key>/episode_000000.mp4   feature's dtype is "video"

This module only ever reads files a viewer needs -- it never imports the
`lerobot` package itself, just parses the on-disk layout directly with
pyarrow/PIL/OpenCV, keeping this GUI's dependencies light.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from PIL import Image

from .sources import DemoRef, Episode, SourceKind, Task

_BOOKKEEPING_COLUMNS = {"timestamp", "frame_index", "episode_index", "index", "task_index"}


def is_lerobot_dataset(path: Path) -> bool:
    return (Path(path) / "meta" / "info.json").is_file()


def _read_info(root: Path) -> dict:
    with open(root / "meta" / "info.json") as f:
        return json.load(f)


def _read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.is_file():
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def scan_dataset(root: Path) -> list[Task]:
    root = Path(root)
    info = _read_info(root)
    fps = float(info.get("fps", 1))
    episodes = _read_jsonl(root / "meta" / "episodes.jsonl")
    episodes.sort(key=lambda e: e["episode_index"])

    # Group episodes by their task text, preserving first-seen order, so the
    # browser panel shows one entry per language instruction (like one HDF5
    # task file) with its episodes listed underneath (like its demos).
    groups: dict[str, list[dict]] = {}
    for ep in episodes:
        task_text = ", ".join(ep.get("tasks", [])) or "(no instruction)"
        groups.setdefault(task_text, []).append(ep)

    tasks: list[Task] = []
    for idx, (task_text, eps) in enumerate(groups.items()):
        demos = [
            DemoRef(key=f"episode_{ep['episode_index']:06d}", num_steps=int(ep["length"]))
            for ep in eps
        ]
        short = task_text if len(task_text) <= 60 else task_text[:57] + "..."
        tasks.append(
            Task(
                kind=SourceKind.LEROBOT,
                display_name=f"[{root.name}] {short}",
                language_instruction=task_text,
                fps=fps,
                demos=demos,
                source_root=root,
                backend_ref=root,
            )
        )
    return tasks


def _feature_labels(info: dict, feature: str, dim: int) -> list[str]:
    names = info.get("features", {}).get(feature, {}).get("names")
    if isinstance(names, list) and len(names) == dim and all(isinstance(n, str) for n in names):
        return names
    return [f"dim{i}" for i in range(dim)]


def _decode_image_cell(value, shape: tuple[int, ...]) -> np.ndarray:
    if isinstance(value, dict) and value.get("bytes") is not None:
        raw = value["bytes"]
    elif isinstance(value, (bytes, bytearray)):
        raw = bytes(value)
    else:
        return np.asarray(value, dtype=np.uint8).reshape(shape)
    return np.array(Image.open(io.BytesIO(raw)).convert("RGB"))


def _load_video_frames(
    root: Path, info: dict, video_key: str, episode_index: int, chunk: int, num_steps: int
) -> np.ndarray:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            f"Feature '{video_key}' is stored as video, which requires the optional "
            "opencv-python dependency (pip install opencv-python-headless)."
        ) from exc

    video_path = root / info["video_path"].format(
        episode_chunk=chunk, video_key=video_key, episode_index=episode_index
    )
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    cap = cv2.VideoCapture(str(video_path))
    frames = []
    try:
        while True:
            ok, frame_bgr = cap.read()
            if not ok:
                break
            frames.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    finally:
        cap.release()

    if not frames:
        raise RuntimeError(f"Could not decode any frames from {video_path}")
    return np.stack(frames[:num_steps], axis=0)


def load_episode(task: Task, demo_key: str) -> Episode:
    root: Path = task.backend_ref
    info = _read_info(root)
    features: dict = info.get("features", {})
    chunks_size = int(info.get("chunks_size", 1000))

    episode_index = int(demo_key.split("_")[1])
    chunk = episode_index // chunks_size
    data_path = root / info["data_path"].format(episode_chunk=chunk, episode_index=episode_index)
    table = pq.read_table(data_path)
    num_steps = table.num_rows
    columns = {name: table.column(name) for name in table.column_names}

    def is_camera(name: str) -> bool:
        return features.get(name, {}).get("dtype") in ("image", "video")

    def load_camera(name: str) -> np.ndarray | None:
        if name not in features:
            return None
        shape = tuple(features[name].get("shape", ()))
        if features[name]["dtype"] == "video":
            return _load_video_frames(root, info, name, episode_index, chunk, num_steps)
        if name not in columns:
            return None
        cells = columns[name].to_pylist()
        return np.stack([_decode_image_cell(v, shape) for v in cells], axis=0)

    camera_keys = [name for name in features if is_camera(name)]
    primary_key = "image" if "image" in camera_keys else (camera_keys[0] if camera_keys else None)
    wrist_key = "wrist_image" if "wrist_image" in camera_keys else next(
        (k for k in camera_keys if k != primary_key), None
    )

    primary_rgb = load_camera(primary_key) if primary_key else np.zeros((num_steps, 4, 4, 3), np.uint8)
    wrist_rgb = load_camera(wrist_key) if wrist_key else None

    signals: dict[str, tuple[np.ndarray, list[str]]] = {}
    for name, spec in features.items():
        if is_camera(name) or name in _BOOKKEEPING_COLUMNS or name not in columns:
            continue
        raw_values = columns[name].to_pylist()
        if raw_values and not isinstance(raw_values[0], (list, tuple)):
            raw_values = [[v] for v in raw_values]
        arr = np.asarray(raw_values, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr[:, None]
        labels = _feature_labels(info, name, arr.shape[1])
        signals[f"{name} ({arr.shape[1]})"] = (arr, labels)

    return Episode(
        key=demo_key,
        task=task,
        num_steps=num_steps,
        fps=task.fps,
        primary_label=primary_key or "image",
        primary_rgb=primary_rgb,
        wrist_label=wrist_key,
        wrist_rgb=wrist_rgb,
        signals=signals,
    )

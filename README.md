# LIBERO / LeRobot Data Viewer

A Qt (PySide6) desktop application for browsing and visualizing robot demonstration data in
either of two formats:

- **Raw LIBERO HDF5** — the [LIBERO](https://libero-project.github.io/) benchmark's
  `robomimic`/`libero-v1` format (`libero_90`, `libero_10`, `libero_spatial`, etc.): one
  `*_demo.hdf5` file per task, containing many demonstration episodes.
- **LeRobot dataset** (codebase_version v2.x) — the format
  [openpi](https://github.com/Physical-Intelligence/openpi) and other policy-training stacks
  consume for fine-tuning (e.g. what `convert_libero_hdf5_to_lerobot.py` in the `zeyu_openpi`
  project produces from the HDF5 files above).

**File → Open Folder…** auto-detects which format a directory is (a LeRobot dataset root has
`meta/info.json`; otherwise it's treated as a folder of `*.hdf5` files) — you don't need to tell
the app which one you're pointing it at.

It lets you:

- Open a single `*_demo.hdf5` task file, a folder of them, or a LeRobot dataset root
  (**File → Open HDF5 File…** / **Open Folder…**, or the buttons above the task list),
  searchable by name or language instruction. The Open dialogs remember the last folder you
  opened and default to it next time, even across app restarts.
- Select a demonstration/episode and step or play through it frame by frame.
- Watch the primary and wrist camera streams side by side (the wrist view auto-hides if a
  dataset doesn't have one).
- Plot whatever trajectory signals the loaded episode provides — for HDF5: actions,
  end-effector pose, joint states, gripper states, reward; for LeRobot: `state` and `actions`
  (plus any other non-image float columns) — with a cursor synced to the current playback frame.

## Data formats

### Raw LIBERO HDF5

Each `*_demo.hdf5` file holds one task's demonstrations:

```
data/                                  (attrs: env_name, bddl_file_name, num_demos,
                                         problem_info.language_instruction,
                                         env_args.env_kwargs.{camera_names,control_freq}, ...)
  demo_0/
    actions          (T, 7)   float64
    rewards          (T,)     uint8
    dones            (T,)     uint8
    robot_states     (T, 9)   float64
    states           (T, 51)  float64
    obs/
      agentview_rgb     (T, 128, 128, 3) uint8
      eye_in_hand_rgb   (T, 128, 128, 3) uint8
      ee_pos            (T, 3)  float64
      ee_ori            (T, 3)  float64
      ee_states         (T, 6)  float64
      joint_states      (T, 7)  float64
      gripper_states    (T, 2)  float64
  demo_1/
    ...
```

The camera images are rendered by MuJoCo's OpenGL offscreen renderer, whose row order is
bottom-to-top, so the HDF5 backend flips frames vertically before display.

### LeRobot dataset

A dataset root looks like:

```
meta/
  info.json          fps, per-feature dtype/shape/names, data_path/video_path templates
  tasks.jsonl         {task_index, task}
  episodes.jsonl       {episode_index, tasks: [instruction, ...], length}
data/
  chunk-000/
    episode_000000.parquet   per-frame columns; image features store PNG bytes inline
                              when their dtype is "image" (as produced by the converter
                              above), decoded on the fly for display
videos/                       per-episode mp4s, one per camera, when a feature's
  chunk-000/<video_key>/episode_000000.mp4   dtype is "video" instead (decoded via OpenCV)
```

Episodes are grouped in the task list by their shared language instruction, mirroring how each
HDF5 file becomes one task entry. The viewer never imports the `lerobot` package itself — it
reads the parquet/JSONL files directly with `pyarrow`/`Pillow`/OpenCV, keeping the dependency
footprint light.

## Option 1: Run natively (recommended for local development)

Requires Python 3.10+ and a working display (this is a desktop GUI app, not a web app).

```bash
cd libero_hdf5_viewer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Point it at a LIBERO HDF5 data directory (e.g. libero_90) and launch:
python -m libero_viewer.main --data-dir /data/zeyu/PHD_LAB/Amazon_Project/libero_100/libero_90

# ...or a single task file:
python -m libero_viewer.main --data-dir /path/to/KITCHEN_SCENE1_..._demo.hdf5

# ...or a LeRobot dataset root (detected automatically -- must contain meta/info.json):
python -m libero_viewer.main --data-dir /path/to/lerobot_dataset_root
```

`--data-dir` (alias `--path`) accepts a single `*_demo.hdf5` file, a folder of them, or a
LeRobot dataset root -- format is auto-detected. Or install it as a package and use the
`libero-viewer` console script:

```bash
pip install -e .
libero-viewer --path /path/to/libero_90            # HDF5 folder
libero-viewer --path /path/to/some_task_demo.hdf5  # single HDF5 file
libero-viewer --path /path/to/lerobot_dataset_root  # LeRobot dataset
```

If no path is given at launch, use **File → Open HDF5 File…** or **File → Open Folder…** in the
app (also available as buttons above the task list), or set the `LIBERO_DATA_DIR` environment
variable.

## Option 2: Run via Docker

Qt is a native desktop toolkit, so the container needs access to an X11 display on the host.
This works out of the box on Linux hosts (which is what this repo assumes).

**Important — mounting and the in-app "Open…" dialogs:** a container only sees paths you've
explicitly bind-mounted into it. The scripts below mount a broader host directory (e.g.
`/data/zeyu/PHD_LAB/Amazon_Project`) into the container at the **same absolute path** it has on
the host (an identity mount), rather than remapping it to something like `/data`. That way,
`File → Open HDF5 File…` / `File → Open Folder…` inside the app show real, navigable host paths
— you can browse anywhere under the mounted root (HDF5 directories and LeRobot dataset roots
alike), not just the one directory passed on the command line.

**Persisting the "last opened folder" across container runs:** each `docker run --rm` starts
from a clean container, so anything not in a bind-mounted volume (like the app's remembered
last-opened folder, stored via Qt's `QSettings`) would normally be lost when the container
exits. `run_docker.sh` and `docker-compose.yml` mount `./.viewer-settings` (created on first run)
to the container's settings directory to fix this, so the Open dialogs still default to wherever
you last opened something even after the container has been removed and relaunched.

### Quick start

```bash
cd libero_hdf5_viewer
./run_docker.sh [path-to-open-on-launch] [mount-root]

# e.g. open libero_90 directly, with the whole Amazon_Project tree browsable:
./run_docker.sh /data/zeyu/PHD_LAB/Amazon_Project/libero_100/libero_90 \
                /data/zeyu/PHD_LAB/Amazon_Project
```

Both arguments are optional: `path-to-open-on-launch` defaults to `libero_100/libero_90` next
to this script, and `mount-root` defaults to its parent (`Amazon_Project`). The script builds
the image, grants it access to your X server via `xhost`, and bind-mounts `mount-root` read-only
at the identical path inside the container.

### Manual steps

```bash
cd libero_hdf5_viewer
docker build -t libero-hdf5-viewer .

xhost +local:docker   # allow the container to connect to your X server

MOUNT_ROOT=/data/zeyu/PHD_LAB/Amazon_Project
mkdir -p .viewer-settings && chmod 777 .viewer-settings
docker run --rm -it \
    --network host --ipc host \
    -e DISPLAY=$DISPLAY -e QT_QPA_PLATFORM=xcb \
    -e LIBERO_DATA_DIR="$MOUNT_ROOT/libero_100/libero_90" \
    -e HOME=/home/viewer \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "$MOUNT_ROOT:$MOUNT_ROOT:ro" \
    -v "$(pwd)/.viewer-settings:/home/viewer/.config/libero-viewer:rw" \
    libero-hdf5-viewer
```

### Or with docker compose

```bash
cd libero_hdf5_viewer
mkdir -p .viewer-settings && chmod 777 .viewer-settings
MOUNT_ROOT=/data/zeyu/PHD_LAB/Amazon_Project \
LIBERO_DATA_DIR=/data/zeyu/PHD_LAB/Amazon_Project/libero_100/libero_90 \
    docker compose up --build
```

### Troubleshooting X11

- `xhost +local:docker` only needs to be run once per host session. Run `xhost -local:docker`
  afterwards to revoke access again.
- If you get `qt.qpa.xcb: could not connect to display`, confirm `$DISPLAY` is set on the host
  (`echo $DISPLAY`, typically `:0` or `:1`) and that you're running this on the machine with the
  physical/X display, not over a plain SSH session without `-X`/`-Y` forwarding.
- Remote/headless servers: SSH in with `ssh -X user@host` (X11 forwarding) before running
  `run_docker.sh`, or run the app inside a VNC/`Xvfb` session.

## Project layout

```
libero_hdf5_viewer/
├── src/libero_viewer/
│   ├── sources.py         # Shared Task/DemoRef/Episode types + format auto-detection & dispatch
│   ├── data_model.py      # HDF5 backend: directory scan (metadata only) + per-episode loading
│   ├── lerobot_source.py  # LeRobot backend: meta/*.jsonl scan + per-episode parquet/video loading
│   ├── workers.py         # QThread wrappers so scanning/loading never blocks the UI
│   ├── player.py          # Frame-index playback timer (play/pause/step/speed)
│   ├── video_widget.py    # Camera frame display widget
│   ├── plot_widget.py     # Embedded matplotlib trajectory plot with frame cursor
│   ├── main_window.py     # Main window: task/demo browser + viewer + controls
│   └── main.py            # CLI entry point
├── pyproject.toml
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── run_docker.sh
```

Both backends produce the same `Task` / `DemoRef` / `Episode` dataclasses (`sources.py`), so
`main_window.py`, `video_widget.py`, and `plot_widget.py` don't know or care which format is
loaded -- they just render whatever camera streams and signals the active `Episode` provides.

## Notes

- Directory scanning only reads cheap metadata (HDF5 group/dataset *attributes*, or LeRobot's
  `meta/*.jsonl` files) -- no image or trajectory arrays -- so browsing even large directories
  like `libero_90` (90 files) is fast.
- Selecting a demonstration/episode loads its full arrays (camera streams, actions, and
  states/joints) into memory -- a few tens of MB per episode -- for smooth scrubbing.
- Data directories are mounted read-only; the app never modifies source `.hdf5` or LeRobot files.
- The last folder/file opened is remembered via Qt's `QSettings` and reused as the Open
  dialogs' starting directory next time -- natively that's
  `~/.config/libero-viewer/LiberoViewer.conf`; under Docker it's the bind-mounted
  `.viewer-settings/LiberoViewer.conf` described above.

## Smoke test

`tests/smoke_test.py` drives the real `MainWindow` (scan → select task → select demo →
seek → play → open a single HDF5 file) against a mounted HDF5 directory at `/data`, with
`QT_QPA_PLATFORM=offscreen` so it can run without a display -- useful for verifying the Docker
image or CI:

```bash
docker run --rm \
    -e QT_QPA_PLATFORM=offscreen \
    -v /path/to/libero_90:/data:ro \
    -v "$(pwd)/tests/smoke_test.py:/app/smoke_test.py:ro" \
    --entrypoint python3 \
    libero-hdf5-viewer:latest /app/smoke_test.py
```

If you also mount a LeRobot dataset root at `/lerobot_test`, the same run additionally opens
it and verifies an episode loads with both camera streams and its `state`/`actions` signals;
this part is skipped automatically if nothing is mounted there:

```bash
docker run --rm \
    -e QT_QPA_PLATFORM=offscreen \
    -v /path/to/libero_90:/data:ro \
    -v /path/to/a/lerobot_dataset_root:/lerobot_test:ro \
    -v "$(pwd)/tests/smoke_test.py:/app/smoke_test.py:ro" \
    --entrypoint python3 \
    libero-hdf5-viewer:latest /app/smoke_test.py
```

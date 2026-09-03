"""Headless smoke test: drives the real MainWindow against mounted LIBERO HDF5
data (/data) and, if present, a mounted LeRobot dataset (/lerobot_test).

Run inside the container with QT_QPA_PLATFORM=offscreen.
"""
from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, "/app/src")
from libero_viewer.main_window import MainWindow  # noqa: E402
from libero_viewer.sources import SourceKind  # noqa: E402

app = QApplication(sys.argv)
window = MainWindow(initial_path="/data")
window.show()

LEROBOT_FIXTURE = Path("/lerobot_test")


def check_scanned():
    n_tasks = window._task_list.count()
    assert n_tasks > 0, "no tasks scanned"
    print(f"OK: scanned {n_tasks} HDF5 tasks, list widget populated")
    window._task_list.setCurrentRow(0)
    QTimer.singleShot(1000, check_demo_loaded)


def check_demo_loaded():
    episode = window._current_episode
    assert episode is not None, "episode did not load"
    assert episode.task.kind is SourceKind.HDF5
    print(f"OK: HDF5 episode loaded — {episode.key}, {episode.num_steps} steps")
    assert window._frame_slider.maximum() == episode.num_steps - 1
    window._player.seek(5)
    QTimer.singleShot(300, check_frame_advanced)


def check_frame_advanced():
    idx = window._frame_slider.value()
    assert idx == 5, f"expected frame 5, got {idx}"
    pix = window._primary_view._image_label.pixmap()
    assert pix is not None and not pix.isNull(), "primary camera frame not rendered"
    assert window._wrist_view.isVisible(), "wrist camera should be visible for HDF5 episodes"
    print(f"OK: seeked to frame {idx}, primary pixmap size {pix.size().toTuple()}")

    window._player.play()
    QTimer.singleShot(500, check_playing)


def check_playing():
    assert window._player.is_playing(), "player did not start"
    idx_before = window._frame_slider.value()
    QTimer.singleShot(500, lambda: check_advanced_while_playing(idx_before))


def check_advanced_while_playing(idx_before):
    idx_after = window._frame_slider.value()
    assert idx_after > idx_before, f"frame did not advance: {idx_before} -> {idx_after}"
    print(f"OK: playback advanced frame {idx_before} -> {idx_after}")
    window._player.pause()

    open_single_file()


def open_single_file():
    single_file = next(iter(sorted(Path("/data").glob("*.hdf5"))))
    window._open_path(single_file)
    QTimer.singleShot(1000, lambda: check_single_file_opened(single_file))


def check_single_file_opened(single_file):
    assert window._task_list.count() == 1, (
        f"expected 1 task after opening a single HDF5 file, got {window._task_list.count()}"
    )
    assert window._tasks[0].backend_ref == single_file
    print(f"OK: opened single HDF5 file {single_file.name} -> 1 task listed")

    if LEROBOT_FIXTURE.is_dir():
        open_lerobot_dataset()
    else:
        print("SKIP: no LeRobot fixture mounted at /lerobot_test, skipping that part")
        print("SMOKE TEST PASSED")
        app.quit()


def open_lerobot_dataset():
    window._open_path(LEROBOT_FIXTURE)
    QTimer.singleShot(1000, check_lerobot_scanned)


def check_lerobot_scanned():
    assert window._tasks, "no LeRobot tasks scanned"
    assert window._tasks[0].kind is SourceKind.LEROBOT
    print(f"OK: scanned LeRobot dataset -> {len(window._tasks)} task(s)")
    window._task_list.setCurrentRow(0)
    QTimer.singleShot(1000, check_lerobot_episode_loaded)


def check_lerobot_episode_loaded():
    episode = window._current_episode
    assert episode is not None, "LeRobot episode did not load"
    assert episode.task.kind is SourceKind.LEROBOT
    assert episode.primary_rgb.shape[1:] == (128, 128, 3), episode.primary_rgb.shape
    assert episode.wrist_rgb is not None
    assert "state (8)" in episode.signals, list(episode.signals.keys())
    assert "actions (7)" in episode.signals, list(episode.signals.keys())
    print(
        f"OK: LeRobot episode loaded — {episode.key}, {episode.num_steps} steps, "
        f"signals={list(episode.signals.keys())}"
    )

    window._player.seek(3)
    QTimer.singleShot(300, check_lerobot_frame_rendered)


def check_lerobot_frame_rendered():
    idx = window._frame_slider.value()
    assert idx == 3, f"expected frame 3, got {idx}"
    pix = window._primary_view._image_label.pixmap()
    assert pix is not None and not pix.isNull(), "LeRobot primary camera frame not rendered"
    assert window._wrist_view.isVisible()
    print(f"OK: LeRobot frame {idx} rendered, pixmap size {pix.size().toTuple()}")
    print("SMOKE TEST PASSED")
    app.quit()


QTimer.singleShot(1500, check_scanned)
QTimer.singleShot(30000, lambda: (_ for _ in ()).throw(TimeoutError("smoke test timed out")))

sys.exit(app.exec())

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from . import sources
from .player import Player
from .plot_widget import TrajectoryPlot
from .video_widget import CameraView
from .workers import LoadEpisodeWorker, ScanWorker

_KIND_LABELS = {
    sources.SourceKind.HDF5: "raw LIBERO HDF5",
    sources.SourceKind.LEROBOT: "LeRobot dataset",
}

_SETTINGS_ORG = "libero-viewer"
_SETTINGS_APP = "LiberoViewer"
_SETTINGS_KEY_LAST_DIR = "last_opened_dir"


class MainWindow(QMainWindow):
    def __init__(self, initial_path: str | None = None):
        super().__init__()
        self.setWindowTitle("LIBERO / LeRobot Data Viewer")
        self.resize(1280, 820)

        self._tasks: list[sources.Task] = []
        self._current_task: sources.Task | None = None
        self._current_episode: sources.Episode | None = None
        self._scan_worker: ScanWorker | None = None
        self._load_worker: LoadEpisodeWorker | None = None

        self._settings = QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        self._last_opened_dir: str | None = self._settings.value(_SETTINGS_KEY_LAST_DIR, type=str) or None

        self._player = Player(self)
        self._player.frame_changed.connect(self._on_frame_changed)
        self._player.playing_changed.connect(self._on_playing_changed)

        self._build_ui()

        if initial_path:
            self._open_path(Path(initial_path))

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)

        splitter = QSplitter(Qt.Orientation.Horizontal, root)
        outer.addWidget(splitter)

        splitter.addWidget(self._build_browser_panel())
        splitter.addWidget(self._build_viewer_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 940])

        self.setStatusBar(QStatusBar(self))
        self._build_menu()

    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")

        open_file_action = file_menu.addAction("Open HDF5 File…")
        open_file_action.setShortcut("Ctrl+O")
        open_file_action.triggered.connect(self._prompt_open_file)

        open_dir_action = file_menu.addAction("Open Folder…")
        open_dir_action.setShortcut("Ctrl+Shift+O")
        open_dir_action.triggered.connect(self._prompt_open_directory)

        file_menu.addSeparator()
        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def _build_browser_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)

        open_row = QHBoxLayout()
        open_file_btn = QPushButton("Open HDF5 File…", panel)
        open_file_btn.clicked.connect(self._prompt_open_file)
        open_dir_btn = QPushButton("Open Folder…", panel)
        open_dir_btn.setToolTip(
            "A folder of *.hdf5 task files, or a LeRobot dataset root "
            "(a folder containing meta/info.json) -- format is auto-detected."
        )
        open_dir_btn.clicked.connect(self._prompt_open_directory)
        open_row.addWidget(open_file_btn)
        open_row.addWidget(open_dir_btn)
        layout.addLayout(open_row)

        self._dir_label = QLabel("No file or directory loaded", panel)
        self._dir_label.setWordWrap(True)
        self._dir_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._dir_label)

        self._task_filter = QLineEdit(panel)
        self._task_filter.setPlaceholderText("Filter tasks…")
        self._task_filter.textChanged.connect(self._apply_task_filter)
        layout.addWidget(self._task_filter)

        layout.addWidget(QLabel("Tasks", panel))
        self._task_list = QListWidget(panel)
        self._task_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._task_list.currentItemChanged.connect(self._on_task_selected)
        layout.addWidget(self._task_list, 2)

        layout.addWidget(QLabel("Demonstrations / Episodes", panel))
        self._demo_list = QListWidget(panel)
        self._demo_list.currentItemChanged.connect(self._on_demo_selected)
        layout.addWidget(self._demo_list, 1)

        return panel

    def _build_viewer_panel(self) -> QWidget:
        panel = QWidget(self)
        layout = QVBoxLayout(panel)

        self._instruction_label = QLabel("Select a task and demonstration to begin.", panel)
        self._instruction_label.setWordWrap(True)
        self._instruction_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        layout.addWidget(self._instruction_label)

        video_row = QHBoxLayout()
        self._primary_view = CameraView(parent=panel)
        self._wrist_view = CameraView(parent=panel)
        video_row.addWidget(self._primary_view, 1)
        video_row.addWidget(self._wrist_view, 1)
        layout.addLayout(video_row, 3)

        layout.addWidget(self._build_transport_controls())

        self._plot = TrajectoryPlot(panel)
        self._plot.signals_changed.connect(self._on_signals_changed)
        plot_box = QGroupBox("Trajectory signals", panel)
        plot_layout = QVBoxLayout(plot_box)

        signal_row = QHBoxLayout()
        signal_row.addWidget(QLabel("Signal:"))
        self._signal_combo = QComboBox(panel)
        self._signal_combo.currentTextChanged.connect(self._plot.set_signal)
        signal_row.addWidget(self._signal_combo)
        signal_row.addStretch(1)
        plot_layout.addLayout(signal_row)
        plot_layout.addWidget(self._plot)

        layout.addWidget(plot_box, 2)

        return panel

    def _build_transport_controls(self) -> QWidget:
        box = QGroupBox("Playback", self)
        layout = QVBoxLayout(box)

        slider_row = QHBoxLayout()
        self._frame_label = QLabel("0 / 0", box)
        self._frame_label.setMinimumWidth(80)
        self._frame_slider = QSlider(Qt.Orientation.Horizontal, box)
        self._frame_slider.setMinimum(0)
        self._frame_slider.setMaximum(0)
        self._frame_slider.valueChanged.connect(self._on_slider_moved)
        slider_row.addWidget(self._frame_slider, 1)
        slider_row.addWidget(self._frame_label)
        layout.addLayout(slider_row)

        button_row = QHBoxLayout()
        self._prev_btn = QPushButton("⏮ Prev", box)
        self._prev_btn.clicked.connect(lambda: self._player.step(-1))
        self._play_btn = QPushButton("▶ Play", box)
        self._play_btn.clicked.connect(self._player.toggle)
        self._next_btn = QPushButton("Next ⏭", box)
        self._next_btn.clicked.connect(lambda: self._player.step(1))

        self._speed_combo = QComboBox(box)
        self._speed_combo.addItems(["0.25x", "0.5x", "1x", "2x", "4x"])
        self._speed_combo.setCurrentText("1x")
        self._speed_combo.currentTextChanged.connect(self._on_speed_changed)

        button_row.addWidget(self._prev_btn)
        button_row.addWidget(self._play_btn)
        button_row.addWidget(self._next_btn)
        button_row.addStretch(1)
        button_row.addWidget(QLabel("Speed:"))
        button_row.addWidget(self._speed_combo)
        layout.addLayout(button_row)

        return box

    # -------------------------------------------------------------- actions
    def _start_dir(self) -> str:
        if self._current_task is not None:
            return str(self._current_task.source_root)
        if self._last_opened_dir and Path(self._last_opened_dir).is_dir():
            return self._last_opened_dir
        return str(Path.home())

    def _prompt_open_file(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self, "Open LIBERO HDF5 file", self._start_dir(), "LIBERO HDF5 files (*.hdf5)"
        )
        if path:
            self._open_path(Path(path))

    def _prompt_open_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Open LIBERO / LeRobot data folder", self._start_dir())
        if directory:
            self._open_path(Path(directory))

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "Not found", f"{path} does not exist.")
            return
        self._dir_label.setText(f"Scanning {path} …")
        self.statusBar().showMessage(f"Scanning {path} ...")
        self._scan_worker = ScanWorker(path, self)
        self._scan_worker.finished_ok.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(self._on_scan_failed)
        self._scan_worker.start()

    def _on_scan_failed(self, message: str) -> None:
        self.statusBar().showMessage("Scan failed")
        QMessageBox.critical(self, "Failed to scan directory", message)

    def _on_scan_finished(self, tasks: list[sources.Task]) -> None:
        self._tasks = tasks
        if not tasks:
            self._dir_label.setText("No LIBERO HDF5 files or LeRobot dataset found")
        else:
            kind_label = _KIND_LABELS[tasks[0].kind]
            root = tasks[0].source_root
            self._dir_label.setText(f"{root}  ({kind_label}, {len(tasks)} task(s))")
            self._last_opened_dir = str(root)
            self._settings.setValue(_SETTINGS_KEY_LAST_DIR, self._last_opened_dir)
        self.statusBar().showMessage(f"Loaded {len(tasks)} task(s)")
        self._apply_task_filter(self._task_filter.text())

    def _apply_task_filter(self, text: str) -> None:
        self._task_list.clear()
        text = text.strip().lower()
        for task in self._tasks:
            haystack = f"{task.display_name} {task.language_instruction}".lower()
            if text and text not in haystack:
                continue
            item = QListWidgetItem(task.display_name)
            item.setData(Qt.ItemDataRole.UserRole, task)
            item.setToolTip(task.language_instruction)
            self._task_list.addItem(item)

    def _on_task_selected(self, current: QListWidgetItem | None, _previous) -> None:
        self._demo_list.clear()
        self._player.stop()
        if current is None:
            self._current_task = None
            return
        task: sources.Task = current.data(Qt.ItemDataRole.UserRole)
        self._current_task = task
        kind_label = _KIND_LABELS[task.kind]
        self._instruction_label.setText(f'"{task.language_instruction}"  —  {kind_label}')
        for demo in task.demos:
            item = QListWidgetItem(f"{demo.key}  ({demo.num_steps} steps)")
            item.setData(Qt.ItemDataRole.UserRole, demo.key)
            self._demo_list.addItem(item)
        if self._demo_list.count() > 0:
            self._demo_list.setCurrentRow(0)

    def _on_demo_selected(self, current: QListWidgetItem | None, _previous) -> None:
        self._player.stop()
        if current is None or self._current_task is None:
            return
        demo_key = current.data(Qt.ItemDataRole.UserRole)
        self.statusBar().showMessage(f"Loading {self._current_task.display_name} / {demo_key} …")
        self._load_worker = LoadEpisodeWorker(self._current_task, demo_key, self)
        self._load_worker.finished_ok.connect(self._on_episode_loaded)
        self._load_worker.failed.connect(self._on_episode_load_failed)
        self._load_worker.start()

    def _on_episode_load_failed(self, message: str) -> None:
        self.statusBar().showMessage("Failed to load demonstration")
        QMessageBox.critical(self, "Failed to load demonstration", message)

    def _on_episode_loaded(self, episode: sources.Episode) -> None:
        self._current_episode = episode
        self._plot.set_episode(episode)
        self._frame_slider.setMaximum(max(episode.num_steps - 1, 0))
        self._player.configure(episode.num_steps, episode.fps)

        self._primary_view.set_title(episode.primary_label)
        if episode.wrist_rgb is not None:
            self._wrist_view.set_title(episode.wrist_label or "wrist")
            self._wrist_view.setVisible(True)
        else:
            self._wrist_view.clear()
            self._wrist_view.setVisible(False)

        self.statusBar().showMessage(
            f"{episode.task.display_name} / {episode.key}: {episode.num_steps} steps @ "
            f"{episode.fps:g} Hz"
        )

    def _on_signals_changed(self, names: list[str]) -> None:
        self._signal_combo.blockSignals(True)
        self._signal_combo.clear()
        self._signal_combo.addItems(names)
        self._signal_combo.blockSignals(False)

    def _on_slider_moved(self, value: int) -> None:
        if self._frame_slider.hasFocus():
            self._player.seek(value)

    def _on_speed_changed(self, text: str) -> None:
        self._player.set_speed(float(text.rstrip("x")))

    def _on_playing_changed(self, playing: bool) -> None:
        self._play_btn.setText("⏸ Pause" if playing else "▶ Play")

    def _on_frame_changed(self, index: int) -> None:
        episode = self._current_episode
        if episode is None:
            return
        self._frame_slider.blockSignals(True)
        self._frame_slider.setValue(index)
        self._frame_slider.blockSignals(False)
        self._frame_label.setText(f"{index} / {max(episode.num_steps - 1, 0)}")

        self._primary_view.set_frame(episode.primary_rgb[index])
        if episode.wrist_rgb is not None:
            self._wrist_view.set_frame(episode.wrist_rgb[index])
        self._plot.set_frame_index(index)

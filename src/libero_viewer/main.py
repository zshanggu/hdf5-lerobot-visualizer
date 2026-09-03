from __future__ import annotations

import argparse
import os
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LIBERO / LeRobot demonstration data viewer")
    parser.add_argument(
        "--data-dir",
        "--path",
        dest="data_dir",
        default=os.environ.get("LIBERO_DATA_DIR"),
        help="A single LIBERO *_demo.hdf5 file, a directory containing several of them, "
        "or a LeRobot dataset root (a directory with meta/info.json) -- format is "
        "auto-detected (default: $LIBERO_DATA_DIR if set)",
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args(sys.argv[1:])
    app = QApplication(sys.argv)
    app.setApplicationName("LIBERO / LeRobot Data Viewer")
    window = MainWindow(initial_path=args.data_dir)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

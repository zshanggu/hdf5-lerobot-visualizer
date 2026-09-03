#!/usr/bin/env bash
# Build (if needed) and run the LIBERO HDF5 Viewer in Docker with X11
# forwarding to the host display.
#
# Usage:
#   ./run_docker.sh [path-to-open-on-launch] [mount-root]
#
# `mount-root` is bind-mounted into the container at the SAME absolute path
# (read-only), so the in-app "Open File…" / "Open Folder…" dialogs can
# browse anywhere under it exactly as they appear on the host -- not just
# the one directory passed on the command line. Defaults to the Amazon
# Project directory two levels up from this script, since that's what
# typically holds all the LIBERO data variants (libero_100, libero_spatial, ...).
#
# Defaults to opening ../libero_100/libero_90 relative to this script.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPEN_PATH="${1:-$SCRIPT_DIR/../libero_100/libero_90}"
MOUNT_ROOT="${2:-$SCRIPT_DIR/..}"

if [[ ! -e "$OPEN_PATH" ]]; then
    echo "error: path not found: $OPEN_PATH" >&2
    exit 1
fi
if [[ ! -d "$MOUNT_ROOT" ]]; then
    echo "error: mount root not found: $MOUNT_ROOT" >&2
    exit 1
fi
OPEN_PATH="$(cd "$(dirname "$OPEN_PATH")" && pwd)/$(basename "$OPEN_PATH")"
MOUNT_ROOT="$(cd "$MOUNT_ROOT" && pwd)"

if [[ "$OPEN_PATH" != "$MOUNT_ROOT"* ]]; then
    echo "error: $OPEN_PATH is not under mount root $MOUNT_ROOT" >&2
    echo "       pass it explicitly as the 2nd argument: ./run_docker.sh <path> <mount-root>" >&2
    exit 1
fi

# Where the app's "last opened folder" (and other Qt settings) persist across
# runs. Owned by the container's fixed `viewer` user (uid 1000), which won't
# generally match your host uid, so it's made world-writable rather than
# requiring a --user override -- fine for a local single-user dev tool.
SETTINGS_DIR="$SCRIPT_DIR/.viewer-settings"
mkdir -p "$SETTINGS_DIR"
chmod 777 "$SETTINGS_DIR"

IMAGE_TAG="libero-hdf5-viewer:latest"
docker build -t "$IMAGE_TAG" "$SCRIPT_DIR"

xhost +local:docker >/dev/null 2>&1 || echo "warning: xhost not available; X11 access may fail"

docker run --rm -it \
    --network host \
    --ipc host \
    -e DISPLAY="${DISPLAY:-:0}" \
    -e QT_QPA_PLATFORM=xcb \
    -e LIBERO_DATA_DIR="$OPEN_PATH" \
    -e HOME=/home/viewer \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "$MOUNT_ROOT:$MOUNT_ROOT:ro" \
    -v "$SETTINGS_DIR:/home/viewer/.config/libero-viewer:rw" \
    "$IMAGE_TAG"

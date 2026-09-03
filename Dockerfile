FROM python:3.11-slim

# Runtime libraries required by PySide6/Qt6 (xcb platform plugin) to talk to
# an X11 server for display. No compiler toolchain needed since PySide6
# ships prebuilt wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libegl1 \
        libopengl0 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libdbus-1-3 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-render0 \
        libxcb-shape0 \
        libxcb-shm0 \
        libxcb-sync1 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxcb1 \
        libx11-xcb1 \
        libxext6 \
        libxrender1 \
        libsm6 \
        libice6 \
        libglib2.0-0 \
        libfontconfig1 \
        libfreetype6 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --no-deps -e .

# Run as a non-root user; X11 access is granted via `xhost` on the host,
# not via container privileges.
RUN useradd --create-home --uid 1000 viewer
USER viewer

ENV QT_QPA_PLATFORM=xcb \
    MPLCONFIGDIR=/tmp/matplotlib
# LIBERO_DATA_DIR is intentionally left unset here -- set it at `docker run`
# time to the path you bind-mounted (see run_docker.sh / docker-compose.yml),
# so it matches whatever's actually visible inside the container.
# MPLCONFIGDIR avoids matplotlib trying (and failing) to write its cache to
# $HOME/.config/matplotlib, since only the libero-viewer settings subdir
# under $HOME/.config is bind-mounted writable (see run_docker.sh).

ENTRYPOINT ["libero-viewer"]

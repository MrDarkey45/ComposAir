"""Camera open + readiness check.

Wraps cv2.VideoCapture with a user-facing failure dialog so a packaged
.exe user sees an explanation instead of a silently exiting console.

Failure modes handled:
- VideoCapture cannot open the device at all (no camera, or wrong index)
- VideoCapture opens but the first read returns no frame (camera held by
  another app like Teams / Zoom / OBS, or USB enumeration glitch)

On failure the user gets a Tkinter dialog with a description of the
likely cause and Retry / Quit buttons.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox

import cv2

logger = logging.getLogger(__name__)


def open_camera(
    index: int,
    width: int,
    height: int,
    fps: int,
) -> cv2.VideoCapture | None:
    """Open a camera, retry on failure with a user-visible dialog.

    Returns the opened VideoCapture, or None if the user chose to quit
    rather than retry.
    """
    while True:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            if not _ask_retry(_no_camera_message(index)):
                return None
            continue

        # Apply settings and pull one frame to confirm the device actually streams.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)

        ok, _ = cap.read()
        if not ok:
            cap.release()
            if not _ask_retry(_camera_busy_message(index)):
                return None
            continue

        logger.info(
            "Camera opened: %dx%d @ %.1f FPS (index %d)",
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            cap.get(cv2.CAP_PROP_FPS),
            index,
        )
        return cap


def _ask_retry(message: str) -> bool:
    """Show a modal error dialog with Retry / Quit. Returns True for retry.

    Uses a fresh Tk root and destroys it after, so this can be called
    before any other Tk usage in the app.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    answer = messagebox.askretrycancel(
        title="ComposAir - camera not available",
        message=message,
        icon="warning",
    )
    root.destroy()
    return bool(answer)


def _no_camera_message(index: int) -> str:
    return (
        f"Could not open camera at index {index}.\n\n"
        "Common causes:\n"
        f"  - No camera is connected.\n"
        f"  - The wrong camera_index is set in config.yaml. If you have\n"
        f"    multiple cameras, try 0, 1, or 2.\n"
        f"  - The camera driver is not installed or has crashed.\n\n"
        "Click Retry after plugging in / restarting the camera, or Cancel to quit."
    )


def _camera_busy_message(index: int) -> str:
    return (
        f"Camera at index {index} opened but is not producing frames.\n\n"
        "Almost always this means another app is holding the camera:\n"
        "  - Microsoft Teams, Zoom, Discord, or Skype\n"
        "  - OBS Studio or any streaming software\n"
        "  - A browser tab that asked for camera access\n"
        "  - Windows Camera app\n\n"
        "Close the other app, then click Retry. Click Cancel to quit."
    )
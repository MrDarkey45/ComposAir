"""Camera open + readiness check.

Wraps the platform-appropriate camera capture with a user-facing failure
dialog so a packaged exe / app user sees an explanation instead of a
silently exiting console.

Backends:
- macOS: PyAV (FFmpeg's AVFoundation input device). opencv-python's
  AVFoundation wrapper has a sustained-capture bug on Apple silicon
  that hangs after ~80 frames; PyAV uses a different code path.
- Windows / Linux: cv2.VideoCapture with the platform-default backend
  (DSHOW / V4L2). Works fine for sustained capture there.

Failure modes handled:
- The device cannot be opened (no camera, wrong index, permission denied)
- The device opens but the first read returns no frame (camera held by
  another app)

On failure the user gets a Tkinter dialog with a description of the
likely cause and Retry / Quit buttons.
"""

from __future__ import annotations

import errno
import logging
import sys
import time
import tkinter as tk
from threading import Event, Lock, Thread
from tkinter import messagebox

import cv2

logger = logging.getLogger(__name__)


def open_camera(
    index: int,
    width: int,
    height: int,
    fps: int,
    backend: int = cv2.CAP_DSHOW,
):
    """Open the platform-appropriate camera with a user-visible retry dialog.

    Returns a capture object exposing .read() / .release() / .get(prop),
    or None if the user cancelled. Callers should treat the return value
    opaquely; both PyAVCamera and cv2.VideoCapture implement the surface
    the main loop uses.
    """
    if sys.platform == "darwin":
        return _open_pyav_camera_with_retry(index, width, height, fps)
    return _open_cv2_camera_with_retry(index, width, height, fps, backend)


def read_frame(cap) -> tuple[bool, "cv2.typing.MatLike | None"]:
    """Read one frame. Thin wrapper kept for API stability."""
    return cap.read()


# ---------------------------------------------------------------------------
# macOS / PyAV path
# ---------------------------------------------------------------------------


class PyAVCamera:
    """FFmpeg/PyAV-based camera capture for macOS.

    opencv-python's AVFoundation wrapper hangs sustained capture after
    ~80 frames on Apple silicon (verified by isolating the symptom with
    a 30 s minimal read loop). PyAV uses FFmpeg's AVFoundation input
    device, which is a different code path that handles long sessions
    correctly.

    Decoding runs in a background thread so .read() never blocks on the
    capture pipeline; it always returns the most recently decoded frame.
    Exposes the same .read()/.release()/.get() surface as cv2.VideoCapture
    so the rest of the app doesn't need to care which backend is in use.
    """

    def __init__(
        self,
        index: int,
        width: int,
        height: int,
        fps: int,
        warmup_s: float = 3.0,
    ) -> None:
        # Deferred import: keep PyAV optional so non-Mac users don't
        # need it installed (it would be unused there).
        import av

        self._av = av
        self._container = av.open(
            str(index),
            format="avfoundation",
            options={
                "framerate": str(fps),
                "video_size": f"{width}x{height}",
                # uyvy422 is the native pixel format for most Mac cameras
                # (built-in FaceTime + Continuity Camera). Letting PyAV
                # pick can hit slow / unsupported formats.
                "pixel_format": "uyvy422",
            },
        )
        self._stream = self._container.streams.video[0]
        self._lock = Lock()
        self._latest_frame: "cv2.typing.MatLike | None" = None
        self._latest_ok = False
        self._stop_event = Event()
        self._first_frame_event = Event()
        self._thread = Thread(
            target=self._reader, daemon=True, name="PyAVReader",
        )
        self._thread.start()
        if not self._first_frame_event.wait(timeout=warmup_s):
            logger.warning(
                "PyAVCamera: no frame in %.1fs warmup window", warmup_s,
            )

    def _reader(self) -> None:
        try:
            # The decode generator can raise EAGAIN ("resource temporarily
            # unavailable") when AVFoundation hasn't produced a frame yet
            # for the requested packet - especially when the consumer is
            # running slower than the camera FPS. EAGAIN is recoverable,
            # not fatal: re-enter decode() after a brief backoff. Other
            # FFmpeg errors are treated as fatal.
            while not self._stop_event.is_set():
                try:
                    self._decode_into_latest()
                    # decode() generator exhausted cleanly - shouldn't
                    # happen for a live capture source. Reopen logic in
                    # main.py will handle this case.
                    break
                except BlockingIOError:
                    time.sleep(0.005)
                except self._av.error.FFmpegError as exc:
                    if self._is_eagain(exc):
                        time.sleep(0.005)
                        continue
                    logger.error("PyAVCamera decode error: %s", exc)
                    break
        except Exception:
            logger.exception("PyAVCamera unexpected error")
        finally:
            with self._lock:
                self._latest_ok = False
            self._first_frame_event.set()  # unblock any pending warmup wait

    def _decode_into_latest(self) -> None:
        for frame in self._container.decode(video=0):
            if self._stop_event.is_set():
                return
            try:
                arr = frame.to_ndarray(format="bgr24")
            except Exception as exc:
                logger.warning("PyAVCamera: frame conversion failed: %s", exc)
                continue
            with self._lock:
                self._latest_ok = True
                self._latest_frame = arr
            if not self._first_frame_event.is_set():
                self._first_frame_event.set()

    @staticmethod
    def _is_eagain(exc: Exception) -> bool:
        if getattr(exc, "errno", None) == errno.EAGAIN:
            return True
        return "temporarily unavailable" in str(exc).lower()

    def read(self) -> tuple[bool, "cv2.typing.MatLike | None"]:
        with self._lock:
            return self._latest_ok, self._latest_frame

    def release(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        try:
            self._container.close()
        except Exception:
            pass

    def get(self, prop: int) -> float:
        """Subset of cv2.VideoCapture.get() that the rest of the app reads."""
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return float(self._stream.codec_context.width)
        if prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return float(self._stream.codec_context.height)
        if prop == cv2.CAP_PROP_FPS:
            try:
                return float(self._stream.average_rate or 30)
            except Exception:
                return 30.0
        return 0.0


def _open_pyav_camera_with_retry(
    index: int, width: int, height: int, fps: int,
):
    import av

    while True:
        try:
            cam = PyAVCamera(index, width, height, fps)
        except av.error.FFmpegError as exc:
            logger.warning("PyAV camera open failed: %s", exc)
            if not _ask_retry(_no_camera_message(index)):
                return None
            continue

        ok, _ = cam.read()
        if not ok:
            cam.release()
            if not _ask_retry(_camera_busy_message(index)):
                return None
            continue

        logger.info(
            "Camera opened (PyAV): %dx%d @ %.1f FPS (index %d)",
            int(cam.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            cam.get(cv2.CAP_PROP_FPS),
            index,
        )
        return cam


# ---------------------------------------------------------------------------
# Windows / Linux / cv2 path
# ---------------------------------------------------------------------------


def _open_cv2_camera_with_retry(
    index: int, width: int, height: int, fps: int, backend: int,
) -> "cv2.VideoCapture | None":
    while True:
        cap = cv2.VideoCapture(index, backend)
        if not cap.isOpened():
            cap.release()
            if not _ask_retry(_no_camera_message(index)):
                return None
            continue

        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

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


class ThreadedCamera:
    """cv2.VideoCapture wrapper that drains frames in a background thread.

    Retained for non-macOS use where a slow consumer can still cause the
    backend's frame buffer to fill. On macOS we use PyAVCamera instead,
    which handles this internally via FFmpeg's input device.
    """

    def __init__(self, cap: cv2.VideoCapture, warmup_s: float = 2.0) -> None:
        self._cap = cap
        self._lock = Lock()
        self._latest_frame: "cv2.typing.MatLike | None" = None
        self._latest_ok = False
        self._stop_event = Event()
        self._first_frame_event = Event()
        self._thread = Thread(
            target=self._reader, daemon=True, name="CameraReader",
        )
        self._thread.start()
        if not self._first_frame_event.wait(timeout=warmup_s):
            logger.warning(
                "ThreadedCamera: no frame in %.1fs warmup window", warmup_s,
            )

    def _reader(self) -> None:
        consecutive_failures = 0
        while not self._stop_event.is_set():
            ok, frame = self._cap.read()
            with self._lock:
                self._latest_ok = ok
                if ok:
                    self._latest_frame = frame
            if ok:
                consecutive_failures = 0
                if not self._first_frame_event.is_set():
                    self._first_frame_event.set()
            else:
                consecutive_failures += 1
                if consecutive_failures in (10, 100, 1000):
                    logger.warning(
                        "ThreadedCamera: %d consecutive read failures",
                        consecutive_failures,
                    )
                time.sleep(0.033)

    def read(self) -> tuple[bool, "cv2.typing.MatLike | None"]:
        with self._lock:
            return self._latest_ok, self._latest_frame

    def release(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=1.0)
        self._cap.release()

    def get(self, prop: int) -> float:
        return self._cap.get(prop)


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------


def _ask_retry(message: str) -> bool:
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
    if sys.platform == "darwin":
        permission_hint = (
            "  - Camera permission not granted. Open System Settings →\n"
            "    Privacy & Security → Camera and enable access for\n"
            "    Terminal (or whichever app you launched ComposAir from).\n"
        )
    else:
        permission_hint = "  - The camera driver is not installed or has crashed.\n"
    return (
        f"Could not open camera at index {index}.\n\n"
        "Common causes:\n"
        f"  - No camera is connected.\n"
        f"  - The wrong camera_index is set in config.yaml. If you have\n"
        f"    multiple cameras, try 0, 1, or 2.\n"
        f"{permission_hint}\n"
        "Click Retry after resolving the issue, or Cancel to quit."
    )


def _camera_busy_message(index: int) -> str:
    if sys.platform == "darwin":
        apps = (
            "  - FaceTime, Photo Booth, or QuickTime Player\n"
            "  - Zoom, Teams, Discord, or any video-call app\n"
            "  - A browser tab that requested camera access\n"
            "  - Continuity Camera (iPhone used as a webcam)\n"
        )
        extra = (
            "If no other app is open, check System Settings → Privacy &\n"
            "Security → Camera and confirm access is granted.\n\n"
        )
    else:
        apps = (
            "  - Microsoft Teams, Zoom, Discord, or Skype\n"
            "  - OBS Studio or any streaming software\n"
            "  - A browser tab that asked for camera access\n"
            "  - Windows Camera app\n"
        )
        extra = ""
    return (
        f"Camera at index {index} opened but is not producing frames.\n\n"
        "Almost always this means another app is holding the camera:\n"
        f"{apps}\n"
        f"{extra}"
        "Close the other app, then click Retry. Click Cancel to quit."
    )

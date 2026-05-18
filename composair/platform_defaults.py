"""Per-platform default values for things that don't make sense to hardcode.

The config schema treats the value `"auto"` as a sentinel meaning "ask
this module at runtime." Explicit values in config.yaml always win, so
users can force a specific driver/backend if the auto choice is wrong
for their setup.
"""

from __future__ import annotations

import sys

import cv2

# Audio driver names accepted by FluidSynth. Per-platform sensible defaults
# matching what each OS actually has working out of the box:
#   - dsound      Windows DirectSound (universally available; ~30 ms latency)
#   - coreaudio   macOS Core Audio (universally available)
#   - pulseaudio  Linux PulseAudio (most distros; alsa/jack are alternatives)
_AUDIO_DRIVER_BY_PLATFORM: dict[str, str] = {
    "win32": "dsound",
    "darwin": "coreaudio",
    "linux": "pulseaudio",
}

# OpenCV camera capture backends per platform. Choosing the right one matters
# more than people expect: on Windows, DSHOW opens fast and is reliable; the
# default MSMF backend is slower and sometimes flaky. On macOS, AVFOUNDATION
# is the only sane choice (the default falls back to QTKit which is removed).
# On Linux, V4L2 is the standard for USB webcams.
_CAMERA_BACKEND_BY_PLATFORM: dict[str, int] = {
    "win32": cv2.CAP_DSHOW,
    "darwin": cv2.CAP_AVFOUNDATION,
    "linux": cv2.CAP_V4L2,
}

_AUTO = "auto"


def resolve_audio_driver(configured: str) -> str:
    """Return the FluidSynth audio driver to use.

    If the config says something other than 'auto', respect it verbatim
    (advanced users may want 'wasapi' on Windows or 'jack' on Linux).
    """
    if configured != _AUTO:
        return configured
    return _AUDIO_DRIVER_BY_PLATFORM.get(sys.platform, "dsound")


def resolve_camera_backend(configured: str) -> int:
    """Return the cv2 VideoCapture backend constant to use.

    Accepted explicit values: 'dshow', 'msmf', 'avfoundation', 'v4l2', 'any'.
    'any' maps to cv2.CAP_ANY which lets OpenCV pick.
    """
    if configured == _AUTO:
        return _CAMERA_BACKEND_BY_PLATFORM.get(sys.platform, cv2.CAP_ANY)
    explicit = {
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
        "avfoundation": cv2.CAP_AVFOUNDATION,
        "v4l2": cv2.CAP_V4L2,
        "any": cv2.CAP_ANY,
    }
    if configured not in explicit:
        raise ValueError(
            f"camera_backend must be one of {sorted(explicit) + [_AUTO]}, "
            f"got '{configured}'"
        )
    return explicit[configured]

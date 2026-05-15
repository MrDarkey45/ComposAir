"""OpenCV overlay rendering.

All drawing happens on a BGR frame in-place. Keeps the main loop free of
imshow/putText noise.
"""

from __future__ import annotations

import cv2
import numpy as np

from .gestures import ALL_FINGERS, Finger, Point2D, THUMB_TIP
from .gm_instruments import name_for
from .scales import ScaleSpec

# MediaPipe hand landmark connections (pairs of indices to draw as bones).
HAND_CONNECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),          # index
    (5, 9), (9, 10), (10, 11), (11, 12),     # middle
    (9, 13), (13, 14), (14, 15), (15, 16),   # ring
    (13, 17), (17, 18), (18, 19), (19, 20),  # pinky
    (0, 17),                                  # palm base
)


def _to_px(p: Point2D, w: int, h: int) -> tuple[int, int]:
    return int(p.x * w), int(p.y * h)


def draw_hand(frame: np.ndarray, landmarks: list[Point2D]) -> None:
    """Draw skeleton + landmarks for a single hand on frame in place."""
    h, w = frame.shape[:2]
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, _to_px(landmarks[a], w, h), _to_px(landmarks[b], w, h),
                 color=(255, 255, 255), thickness=2)
    for lm in landmarks:
        cv2.circle(frame, _to_px(lm, w, h), radius=3, color=(0, 200, 255), thickness=-1)


_PINCH_ACTIVE_COLOR = (0, 255, 0)        # green when finger is pinched
_PINCH_INACTIVE_COLOR = (200, 200, 200)  # grey when finger is at rest


def draw_pinch_indicators(
    frame: np.ndarray,
    landmarks: list[Point2D],
    pinched: dict[Finger, bool],
    distances: dict[Finger, float],
) -> None:
    """Draw one thumb-to-fingertip line per finger and a list of active fingers.

    Each line is green while its finger is pinched, grey otherwise. The
    bottom-left readout lists currently-active fingers and the distance
    value of the closest finger to the thumb (handy for calibration).
    """
    h, w = frame.shape[:2]
    thumb_px = _to_px(landmarks[THUMB_TIP], w, h)

    for finger in ALL_FINGERS:
        color = _PINCH_ACTIVE_COLOR if pinched.get(finger) else _PINCH_INACTIVE_COLOR
        thickness = 4 if pinched.get(finger) else 2
        cv2.line(frame, thumb_px, _to_px(landmarks[finger.tip_index], w, h),
                 color=color, thickness=thickness)

    # Show the smallest distance so users can calibrate against their tightest pinch.
    if distances:
        closest_finger = min(distances, key=lambda f: distances[f])
        cv2.putText(frame,
                    f"closest: {closest_finger.value} d = {distances[closest_finger]:.3f}",
                    (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    active = [f.value.upper() for f in ALL_FINGERS if pinched.get(f)]
    if active:
        cv2.putText(frame, " ".join(active), (10, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, _PINCH_ACTIVE_COLOR, 2)


def draw_fps(frame: np.ndarray, fps: float) -> None:
    """Top-left FPS readout."""
    cv2.putText(frame, f"{fps:.1f} FPS", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def draw_help(frame: np.ndarray) -> None:
    """Bottom-right hint for the keyboard controls."""
    h, w = frame.shape[:2]
    cv2.putText(frame, "Q quit | R record | [ ] instrument", (w - 360, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 2)


def draw_octave_bands(
    frame: np.ndarray,
    boundaries: tuple[float, ...],
    current_band: int,
) -> None:
    """Draw horizontal lines at each band boundary and highlight the current band.

    Boundaries are normalized Y values in (0, 1). The current band is the
    one whose region contains the wrist. We dim the inactive bands so the
    active region pops.
    """
    h, w = frame.shape[:2]
    # Draw boundary lines.
    for y_norm in boundaries:
        y = int(y_norm * h)
        cv2.line(frame, (0, y), (w, y), color=(80, 80, 80), thickness=1)

    # Compute the y-range of the current band and label it.
    # Bands are indexed 0..N-1 from BOTTOM to TOP, so we map band index
    # to a vertical slice of the screen (lower Y = top of screen = higher band).
    num_bands = len(boundaries) + 1
    top_idx = num_bands - 1 - current_band
    top_y = int(top_idx / num_bands * h)
    bot_y = int((top_idx + 1) / num_bands * h)
    cv2.rectangle(frame, (0, top_y), (15, bot_y), color=(0, 200, 255), thickness=-1)
    cv2.putText(frame, f"band {current_band}", (20, top_y + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 255), 2)


def draw_scale_readout(frame: np.ndarray, spec: ScaleSpec, current_octave: int) -> None:
    """Top-right: show the active key, scale, and resolved octave."""
    h, w = frame.shape[:2]
    text = f"{spec.key} {spec.scale_name} | oct {current_octave}"
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
    cv2.putText(frame, text, (w - tw - 10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def draw_instrument_readout(frame: np.ndarray, program: int) -> None:
    """Below the scale readout: show the active GM instrument."""
    h, w = frame.shape[:2]
    text = f"inst {program}: {name_for(program)}"
    (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.putText(frame, text, (w - tw - 10, 165),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 255), 2)


def draw_rec_indicator(frame: np.ndarray, is_recording: bool, event_count: int) -> None:
    """Top-left under the FPS: red REC dot + event count when recording."""
    if not is_recording:
        return
    cv2.circle(frame, (25, 65), 10, color=(0, 0, 255), thickness=-1)
    cv2.putText(frame, f"REC ({event_count} events)", (45, 72),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)


def draw_velocity_readout(
    frame: np.ndarray,
    pinched: dict[Finger, bool],
    last_velocity: dict[Finger, int],
) -> None:
    """Below the scale readout: list each currently-pinched finger and its
    resolved MIDI velocity. Helps the user calibrate how fast a pinch needs
    to be to play loudly.
    """
    h, w = frame.shape[:2]
    y = 60
    for finger in ALL_FINGERS:
        if pinched.get(finger):
            v = last_velocity.get(finger, 0)
            text = f"{finger.value}: v{v}"
            (tw, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.putText(frame, text, (w - tw - 10, y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            y += 24

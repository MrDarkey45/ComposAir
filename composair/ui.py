"""OpenCV overlay rendering.

All drawing happens on a BGR frame in-place. Keeps the main loop free of
imshow/putText noise.
"""

from __future__ import annotations

import cv2
import numpy as np

from .gestures import INDEX_TIP, Point2D, THUMB_TIP

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


def draw_pinch_indicator(
    frame: np.ndarray,
    landmarks: list[Point2D],
    is_pinched: bool,
    normalized_distance: float,
) -> None:
    """Highlight the thumb-index segment and show the live distance value."""
    h, w = frame.shape[:2]
    color = (0, 255, 0) if is_pinched else (200, 200, 200)
    cv2.line(frame, _to_px(landmarks[THUMB_TIP], w, h),
             _to_px(landmarks[INDEX_TIP], w, h), color=color, thickness=4)
    cv2.putText(frame, f"d = {normalized_distance:.3f}",
                (10, h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    if is_pinched:
        cv2.putText(frame, "PINCH", (10, h - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)


def draw_fps(frame: np.ndarray, fps: float) -> None:
    """Top-left FPS readout."""
    cv2.putText(frame, f"{fps:.1f} FPS", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


def draw_help(frame: np.ndarray) -> None:
    """Bottom-right hint for the quit key."""
    h, w = frame.shape[:2]
    cv2.putText(frame, "Q to quit", (w - 130, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 2)

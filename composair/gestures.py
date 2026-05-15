"""Pinch detection with hysteresis.

Pure-ish module: stateless distance math + a small stateful detector.
The detector emits edge-triggered events (PINCH_ON / PINCH_OFF) so the
caller doesn't have to debounce.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto

# MediaPipe HandLandmarker landmark indices.
# https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker
WRIST = 0
MIDDLE_FINGER_MCP = 9
THUMB_TIP = 4
INDEX_TIP = 8


@dataclass(frozen=True)
class Point2D:
    """Normalized (0-1) screen-space landmark coordinate."""

    x: float
    y: float


class PinchEvent(Enum):
    """Edge-triggered pinch transitions."""

    PINCH_ON = auto()
    PINCH_OFF = auto()


def euclidean(a: Point2D, b: Point2D) -> float:
    """Return the 2D distance between two normalized landmarks."""
    return math.hypot(a.x - b.x, a.y - b.y)


def hand_size(landmarks: list[Point2D]) -> float:
    """Return wrist-to-middle-MCP distance, used as a per-hand size unit.

    Normalizing pinch distance by this makes the threshold independent of
    how close to or far from the camera the user holds their hand.
    """
    return euclidean(landmarks[WRIST], landmarks[MIDDLE_FINGER_MCP])


def thumb_index_distance(landmarks: list[Point2D]) -> float:
    """Return raw (un-normalized) thumb-to-index-tip distance."""
    return euclidean(landmarks[THUMB_TIP], landmarks[INDEX_TIP])


def normalized_pinch_distance(landmarks: list[Point2D]) -> float:
    """Return thumb-index distance scaled by hand size. Resolution-independent."""
    size = hand_size(landmarks)
    if size <= 1e-6:
        return float("inf")
    return thumb_index_distance(landmarks) / size


class PinchDetector:
    """Stateful detector that emits PINCH_ON / PINCH_OFF on threshold crossings.

    Two thresholds (on < off) form a hysteresis band so that fingertips
    hovering near the boundary don't produce a stream of flicker events.
    """

    def __init__(self, on_threshold: float, off_threshold: float) -> None:
        if on_threshold >= off_threshold:
            raise ValueError(
                f"on_threshold ({on_threshold}) must be less than off_threshold ({off_threshold})"
            )
        self._on = on_threshold
        self._off = off_threshold
        self._pinched = False

    @property
    def is_pinched(self) -> bool:
        return self._pinched

    def update(self, normalized_distance: float) -> PinchEvent | None:
        """Feed the current normalized distance. Returns an event on transition, else None."""
        if not self._pinched and normalized_distance < self._on:
            self._pinched = True
            return PinchEvent.PINCH_ON
        if self._pinched and normalized_distance > self._off:
            self._pinched = False
            return PinchEvent.PINCH_OFF
        return None

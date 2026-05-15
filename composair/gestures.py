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
MIDDLE_TIP = 12
RING_TIP = 16
PINKY_TIP = 20


class Finger(Enum):
    """The four fingers that can pair with the thumb to form a pinch."""

    INDEX = "index"
    MIDDLE = "middle"
    RING = "ring"
    PINKY = "pinky"

    @property
    def tip_index(self) -> int:
        """The MediaPipe landmark index of this finger's tip."""
        return _FINGER_TIP_INDEX[self]


_FINGER_TIP_INDEX: dict[Finger, int] = {
    Finger.INDEX: INDEX_TIP,
    Finger.MIDDLE: MIDDLE_TIP,
    Finger.RING: RING_TIP,
    Finger.PINKY: PINKY_TIP,
}

# Iteration order for any code that wants a stable per-finger sequence.
ALL_FINGERS: tuple[Finger, ...] = (Finger.INDEX, Finger.MIDDLE, Finger.RING, Finger.PINKY)


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
    """Return raw (un-normalized) thumb-to-index-tip distance.

    Kept for backwards compatibility with Phase 1 tests; prefer
    thumb_to_finger_distance(landmarks, Finger.INDEX) in new code.
    """
    return thumb_to_finger_distance(landmarks, Finger.INDEX)


def thumb_to_finger_distance(landmarks: list[Point2D], finger: Finger) -> float:
    """Return raw thumb-tip to chosen finger-tip distance."""
    return euclidean(landmarks[THUMB_TIP], landmarks[finger.tip_index])


def normalized_pinch_distance(
    landmarks: list[Point2D], finger: Finger = Finger.INDEX
) -> float:
    """Return thumb-to-finger distance scaled by hand size.

    Defaults to the index finger so Phase 1 call sites keep working.
    """
    size = hand_size(landmarks)
    if size <= 1e-6:
        return float("inf")
    return thumb_to_finger_distance(landmarks, finger) / size


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

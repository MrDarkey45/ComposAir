"""Pinch detection with hysteresis.

Pure-ish module: stateless distance math + a small stateful detector.
The detector emits edge-triggered events (PINCH_ON / PINCH_OFF) so the
caller doesn't have to debounce.
"""

from __future__ import annotations

import math
from collections import deque
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


@dataclass(frozen=True)
class VelocityConfig:
    """Static config for VelocityEstimator."""

    min_velocity: int   # MIDI velocity for the slowest pinch (1-127)
    max_velocity: int   # MIDI velocity for the fastest pinch
    window_ms: float    # how far back to look when computing closing speed
    default: int        # fallback when there aren't enough samples yet
    fast_closure_rate: float  # normalized-distance-units per second at which
                              # max_velocity is reached. Speeds above this clamp.


class VelocityEstimator:
    """Tracks recent (time, normalized_distance) samples and maps closing speed
    to a MIDI velocity at trigger time.

    The estimator is per-finger because each finger has its own distance
    series. The model: a "fast pinch" closes the thumb-finger gap quickly,
    producing a steep negative slope in normalized distance over time. The
    magnitude of that slope, clamped to [0, fast_closure_rate], maps
    linearly to [min_velocity, max_velocity].
    """

    def __init__(self, config: VelocityConfig) -> None:
        if not 1 <= config.min_velocity <= 127:
            raise ValueError(f"min_velocity must be in 1-127, got {config.min_velocity}")
        if not 1 <= config.max_velocity <= 127:
            raise ValueError(f"max_velocity must be in 1-127, got {config.max_velocity}")
        if config.min_velocity > config.max_velocity:
            raise ValueError("min_velocity must be <= max_velocity")
        if config.window_ms <= 0:
            raise ValueError(f"window_ms must be > 0, got {config.window_ms}")
        if config.fast_closure_rate <= 0:
            raise ValueError(f"fast_closure_rate must be > 0, got {config.fast_closure_rate}")
        if not 1 <= config.default <= 127:
            raise ValueError(f"default must be in 1-127, got {config.default}")
        self._cfg = config
        self._samples: deque[tuple[float, float]] = deque()

    def add_sample(self, timestamp_s: float, normalized_distance: float) -> None:
        """Record a (time, distance) sample. Old samples outside the window are evicted."""
        self._samples.append((timestamp_s, normalized_distance))
        cutoff = timestamp_s - self._cfg.window_ms / 1000.0
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def estimate_velocity(self) -> int:
        """Compute a MIDI velocity from recent closing speed.

        Returns config.default when there are fewer than 2 samples (no slope
        can be computed). Returns config.min_velocity when motion is flat
        or opening (positive slope). Otherwise scales between min and max.
        """
        if len(self._samples) < 2:
            return self._cfg.default

        # Slope = (last - first) / dt. Negative slope means closing.
        t0, d0 = self._samples[0]
        t1, d1 = self._samples[-1]
        dt = t1 - t0
        if dt <= 1e-6:
            return self._cfg.default

        slope = (d1 - d0) / dt  # negative when closing
        closure_rate = -slope   # positive when closing
        if closure_rate <= 0:
            return self._cfg.min_velocity

        # Clamp into [0, fast_closure_rate] and linearly map to [min, max].
        normalized = min(closure_rate / self._cfg.fast_closure_rate, 1.0)
        velocity = self._cfg.min_velocity + normalized * (
            self._cfg.max_velocity - self._cfg.min_velocity
        )
        return max(1, min(127, int(round(velocity))))

    def clear(self) -> None:
        """Drop all samples. Used on shutdown or after a long tracking gap."""
        self._samples.clear()

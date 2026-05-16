"""One-Euro filter for landmark smoothing.

Reference: G. Casiez, N. Roussel, D. Vogel, "1 Euro Filter: A Simple
Speed-based Low-pass Filter for Noisy Input in Interactive Systems"
(CHI 2012).

The filter combines two low-pass filters: one smooths the raw signal,
one smooths the signal's velocity. The velocity is then used to
adaptively raise the cutoff frequency of the main filter when motion
is fast (less lag) and lower it when motion is slow (more jitter
rejection). The result: stable at rest, responsive when moving.

We apply it per-component (x and y) to each of the 21 landmarks per
hand. Cheap: a few multiplications per landmark per frame.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .gestures import Point2D


@dataclass(frozen=True)
class SmoothingConfig:
    """Static config for HandLandmarkSmoother.

    min_cutoff: Hz. Cutoff frequency when the hand is still. Lower =
        more smoothing of resting jitter. 1.0 is a sensible default.
    beta: dimensionless. Speed coefficient. Higher = less smoothing
        when motion is fast (less lag during fast moves). 0.0 disables
        the speed-adaptive behavior, making this a plain low-pass.
    d_cutoff: Hz. Cutoff for the velocity low-pass. 1.0 is the
        canonical recommendation; rarely needs tuning.
    enabled: if False, the smoother is a passthrough (returns inputs
        verbatim). Lets users disable smoothing entirely via config.
    """

    min_cutoff: float = 1.0
    beta: float = 0.007
    d_cutoff: float = 1.0
    enabled: bool = True


class _LowPass:
    """Exponential low-pass for a single scalar signal."""

    def __init__(self) -> None:
        self._prev: float | None = None

    def filter(self, value: float, alpha: float) -> float:
        if self._prev is None:
            self._prev = value
            return value
        smoothed = alpha * value + (1.0 - alpha) * self._prev
        self._prev = smoothed
        return smoothed

    @property
    def last(self) -> float | None:
        return self._prev


class _OneEuro:
    """One-Euro filter on a single scalar (x or y) component."""

    def __init__(self, config: SmoothingConfig) -> None:
        self._cfg = config
        self._x_filter = _LowPass()
        self._dx_filter = _LowPass()
        self._prev_time: float | None = None
        self._prev_value: float | None = None

    @staticmethod
    def _alpha(cutoff: float, dt: float) -> float:
        # Standard one-euro alpha derivation from cutoff frequency and dt.
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def filter(self, value: float, timestamp_s: float) -> float:
        if not self._cfg.enabled:
            return value

        if self._prev_time is None or self._prev_value is None:
            self._prev_time = timestamp_s
            self._prev_value = value
            self._x_filter.filter(value, 1.0)
            self._dx_filter.filter(0.0, 1.0)
            return value

        dt = timestamp_s - self._prev_time
        if dt <= 0:
            return self._x_filter.last if self._x_filter.last is not None else value

        # Velocity-based cutoff: faster motion -> higher cutoff -> less smoothing.
        dx = (value - self._prev_value) / dt
        dx_smoothed = self._dx_filter.filter(dx, self._alpha(self._cfg.d_cutoff, dt))
        cutoff = self._cfg.min_cutoff + self._cfg.beta * abs(dx_smoothed)
        smoothed = self._x_filter.filter(value, self._alpha(cutoff, dt))

        self._prev_time = timestamp_s
        self._prev_value = value
        return smoothed

    def reset(self) -> None:
        self._x_filter = _LowPass()
        self._dx_filter = _LowPass()
        self._prev_time = None
        self._prev_value = None


class HandLandmarkSmoother:
    """Apply a one-euro filter to each of the 21 landmarks (x and y separately).

    The smoother is stateless across hand-disappear events: call reset()
    when MediaPipe stops reporting a hand so that re-detection does not
    interpolate from a stale position.
    """

    def __init__(self, config: SmoothingConfig, num_landmarks: int = 21) -> None:
        self._cfg = config
        self._x_filters = [_OneEuro(config) for _ in range(num_landmarks)]
        self._y_filters = [_OneEuro(config) for _ in range(num_landmarks)]

    @property
    def enabled(self) -> bool:
        return self._cfg.enabled

    def filter(self, landmarks: list[Point2D], timestamp_s: float) -> list[Point2D]:
        if not self._cfg.enabled:
            return landmarks
        smoothed: list[Point2D] = []
        for i, lm in enumerate(landmarks):
            sx = self._x_filters[i].filter(lm.x, timestamp_s)
            sy = self._y_filters[i].filter(lm.y, timestamp_s)
            smoothed.append(Point2D(sx, sy))
        return smoothed

    def reset(self) -> None:
        for f in self._x_filters:
            f.reset()
        for f in self._y_filters:
            f.reset()

"""Map a pinch (finger + hand Y position) to a MIDI note.

Hand Y is the vertical position of the wrist in normalized [0, 1] screen
coordinates. The screen is divided into N octave bands; lower Y values
(top of screen) play higher octaves, matching the intuition that "high =
high pitch."

Band selection uses hysteresis: once the wrist enters a band, it must
cross noticeably into a neighboring band before the active band switches.
This prevents a pinch right at a boundary from flickering between octaves.
"""

from __future__ import annotations

from dataclasses import dataclass

from .gestures import Finger
from .scales import ScaleSpec, scale_degree_to_midi


@dataclass(frozen=True)
class BandSelectorConfig:
    """Static config for OctaveBandSelector.

    num_bands: how many vertical bands the screen is divided into.
    base_octave: the octave assigned to the LOWEST band (bottom of screen).
        Higher bands count up from there; e.g. base_octave=4 with 3 bands
        gives bottom=4, middle=5, top=6.
    hysteresis: extra distance (in normalized [0,1] Y) past a boundary
        that the wrist must travel before the band changes. Small value;
        roughly 1/10 of a band width is a good default.
    """

    num_bands: int
    base_octave: int
    hysteresis: float


class OctaveBandSelector:
    """Stateful selector that maps a hand Y position to an octave with hysteresis."""

    def __init__(self, config: BandSelectorConfig) -> None:
        if config.num_bands < 1:
            raise ValueError(f"num_bands must be >= 1, got {config.num_bands}")
        if config.hysteresis < 0:
            raise ValueError(f"hysteresis must be >= 0, got {config.hysteresis}")
        self._cfg = config
        # Boundary Y values between adjacent bands; len = num_bands - 1.
        # Bands are equal-width slices of [0, 1].
        self._boundaries = tuple(
            i / config.num_bands for i in range(1, config.num_bands)
        )
        # Start in the middle band so neither extreme is privileged at startup.
        self._current_band = config.num_bands // 2

    @property
    def current_band(self) -> int:
        """The index of the currently selected band (0 = bottom = lowest octave)."""
        return self._current_band

    @property
    def boundaries(self) -> tuple[float, ...]:
        """Y values of the dividing lines between bands, sorted low to high."""
        return self._boundaries

    def update(self, hand_y: float) -> int:
        """Feed the current wrist Y and return the (possibly changed) band index.

        Y is in [0, 1] with 0 at the top of the screen. Band 0 sits at the
        bottom (highest Y), band N-1 at the top (lowest Y), so raising the
        hand raises the octave.

        Hysteresis means a boundary crossing only fires when the wrist
        moves past the boundary by at least self._cfg.hysteresis in the
        direction of travel; small jitter inside that band keeps the
        current band stable.
        """
        # Clamp into [0, 1] in case the wrist briefly leaves the frame.
        y = min(max(hand_y, 0.0), 1.0)
        n = len(self._boundaries)

        # Step up one band at a time while the wrist is well above the
        # next upper boundary; step down while it is well below the next
        # lower boundary. Multiple steps in one update keep the band in
        # sync even after a wrist tracking glitch or a fast hand motion.
        while True:
            upper_boundary_idx = n - 1 - self._current_band
            lower_boundary_idx = n - self._current_band

            if 0 <= upper_boundary_idx < n:
                upper_y = self._boundaries[upper_boundary_idx]
                if y < upper_y - self._cfg.hysteresis:
                    self._current_band += 1
                    continue
            if 0 <= lower_boundary_idx < n:
                lower_y = self._boundaries[lower_boundary_idx]
                if y > lower_y + self._cfg.hysteresis:
                    self._current_band -= 1
                    continue
            break

        return self._current_band

    def octave_for_band(self, band: int) -> int:
        """Convert a band index to an absolute octave number."""
        return self._cfg.base_octave + band


def resolve_midi_note(
    spec: ScaleSpec,
    finger_degrees: dict[Finger, int],
    finger: Finger,
    band: int,
    selector: OctaveBandSelector,
) -> int:
    """Look up a MIDI note for (finger, band) under the current scale and key.

    Pure function over the supplied state; no side effects.
    """
    degree = finger_degrees[finger]
    octave = selector.octave_for_band(band)
    return scale_degree_to_midi(spec, degree, octave)

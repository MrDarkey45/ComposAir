"""Second-hand modulation: map non-playing hand position to a MIDI CC value.

The non-playing hand's vertical position drives a continuous controller
(default CC 74, filter cutoff). Raising the hand opens the filter
(brighter sound); lowering it closes the filter (darker sound).

To keep MIDI traffic sane, the mapper has three filters:
- smoothing: an exponential moving average so small jitter does not
  fire a stream of CC changes
- deadzone: small absolute changes do not emit at all
- update throttling: caller-side, separate; mapper just answers "what
  CC value would I send right now" on demand
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModulationConfig:
    """Static config for ModulationMapper."""

    cc_number: int          # MIDI CC index (0-127)
    smoothing: float        # EMA weight: 0 = no smoothing, ~0.5 = strong
    deadzone: int           # minimum CC delta to actually emit (1-127)
    update_interval_ms: float  # caller throttles at this rate


class ModulationMapper:
    """Stateful: tracks last-sent CC value, computes the next one from a hand Y.

    The hand Y is normalized screen coordinate where 0 = top, 1 = bottom.
    We invert so that raising the hand (lower Y) increases the CC value,
    matching musical intuition: higher = brighter / more open.
    """

    def __init__(self, config: ModulationConfig) -> None:
        if not 0 <= config.cc_number <= 127:
            raise ValueError(f"cc_number must be in 0-127, got {config.cc_number}")
        if not 0.0 <= config.smoothing < 1.0:
            raise ValueError(f"smoothing must be in [0, 1), got {config.smoothing}")
        if config.deadzone < 0:
            raise ValueError(f"deadzone must be >= 0, got {config.deadzone}")
        if config.update_interval_ms <= 0:
            raise ValueError(f"update_interval_ms must be > 0, got {config.update_interval_ms}")
        self._cfg = config
        self._smoothed_y: float | None = None
        self._last_sent: int | None = None

    @property
    def cc_number(self) -> int:
        return self._cfg.cc_number

    @property
    def update_interval_s(self) -> float:
        return self._cfg.update_interval_ms / 1000.0

    @property
    def last_sent(self) -> int | None:
        """The most recent CC value emitted, or None if nothing sent yet."""
        return self._last_sent

    def reset(self) -> None:
        """Drop accumulated state. Call this when the modulation hand leaves frame."""
        self._smoothed_y = None
        self._last_sent = None

    def compute_value(self, hand_y: float) -> int:
        """Update the internal smoothed Y with a new sample and return a CC value.

        The returned int is what we would emit. The caller decides whether
        to actually send it (deadzone check + throttle).
        """
        y = max(0.0, min(1.0, hand_y))
        if self._smoothed_y is None:
            self._smoothed_y = y
        else:
            alpha = 1.0 - self._cfg.smoothing
            self._smoothed_y = alpha * y + (1.0 - alpha) * self._smoothed_y
        # Higher hand position (lower Y) -> higher CC value.
        cc_value = int(round((1.0 - self._smoothed_y) * 127))
        return max(0, min(127, cc_value))

    def should_emit(self, candidate_value: int) -> bool:
        """Return True if the candidate differs from last_sent by more than the deadzone."""
        if self._last_sent is None:
            return True
        return abs(candidate_value - self._last_sent) >= max(1, self._cfg.deadzone)

    def mark_sent(self, value: int) -> None:
        """Caller calls this after successfully emitting the CC."""
        self._last_sent = value
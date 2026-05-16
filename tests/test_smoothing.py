"""Unit tests for the one-Euro filter and HandLandmarkSmoother.

Run from the project root:
    .venv\\Scripts\\python.exe tests\\test_smoothing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from composair.gestures import Point2D
from composair.smoothing import (
    HandLandmarkSmoother,
    SmoothingConfig,
    _OneEuro,
)


def test_disabled_smoother_is_passthrough() -> None:
    cfg = SmoothingConfig(enabled=False)
    sm = HandLandmarkSmoother(cfg)
    landmarks = [Point2D(0.1 * i, 0.2 * i) for i in range(21)]
    out = sm.filter(landmarks, timestamp_s=0.0)
    assert out == landmarks, "disabled smoother must return inputs verbatim"


def test_first_sample_passes_through() -> None:
    """With no history, there is nothing to smooth; first sample should match input."""
    cfg = SmoothingConfig(enabled=True, min_cutoff=1.0, beta=0.0, d_cutoff=1.0)
    f = _OneEuro(cfg)
    out = f.filter(0.5, timestamp_s=0.0)
    assert out == 0.5


def test_steady_signal_remains_steady() -> None:
    """Feeding the same value many times should converge to that value."""
    cfg = SmoothingConfig(enabled=True, min_cutoff=1.0, beta=0.0, d_cutoff=1.0)
    f = _OneEuro(cfg)
    for i in range(60):
        out = f.filter(0.5, timestamp_s=i / 30.0)
    assert abs(out - 0.5) < 1e-6, f"expected ~0.5, got {out}"


def test_jitter_around_constant_is_smoothed() -> None:
    """Small alternating jitter around 0.5 should produce a less-jittery output."""
    cfg = SmoothingConfig(enabled=True, min_cutoff=1.0, beta=0.0, d_cutoff=1.0)
    f = _OneEuro(cfg)
    samples = [0.5 + (0.02 if i % 2 == 0 else -0.02) for i in range(60)]
    outputs = []
    for i, v in enumerate(samples):
        outputs.append(f.filter(v, timestamp_s=i / 30.0))
    # The output range over the last 30 samples should be much smaller
    # than the input range (0.04).
    tail = outputs[-30:]
    input_range = 0.04
    output_range = max(tail) - min(tail)
    assert output_range < input_range * 0.5, (
        f"output range {output_range:.4f} should be << input range {input_range}"
    )


def test_fast_motion_is_responsive_with_beta() -> None:
    """A ramp signal with non-zero beta should track without huge lag."""
    cfg = SmoothingConfig(enabled=True, min_cutoff=1.0, beta=0.1, d_cutoff=1.0)
    f = _OneEuro(cfg)
    # Linear ramp from 0 to 1 over 1 second at 30 Hz.
    for i in range(31):
        v = i / 30.0
        out = f.filter(v, timestamp_s=i / 30.0)
    # Final output should be close to final input. With high beta, lag is small.
    assert out > 0.85, f"expected output near 1.0 after ramp, got {out}"


def test_hand_smoother_filters_all_landmarks() -> None:
    cfg = SmoothingConfig(enabled=True, min_cutoff=1.0, beta=0.0, d_cutoff=1.0)
    sm = HandLandmarkSmoother(cfg)
    # Send a constant hand for many frames.
    hand = [Point2D(0.5, 0.5)] * 21
    for i in range(20):
        out = sm.filter(hand, timestamp_s=i / 30.0)
    # All 21 landmarks should have stabilized at (0.5, 0.5).
    for lm in out:
        assert abs(lm.x - 0.5) < 1e-3 and abs(lm.y - 0.5) < 1e-3


def test_hand_smoother_reset_clears_state() -> None:
    cfg = SmoothingConfig(enabled=True, min_cutoff=0.5, beta=0.0, d_cutoff=1.0)
    sm = HandLandmarkSmoother(cfg)
    hand_a = [Point2D(0.0, 0.0)] * 21
    for i in range(10):
        sm.filter(hand_a, timestamp_s=i / 30.0)
    sm.reset()
    # After reset, the first new sample should pass through verbatim.
    hand_b = [Point2D(1.0, 1.0)] * 21
    out = sm.filter(hand_b, timestamp_s=10.0 / 30.0)
    for lm in out:
        assert lm.x == 1.0 and lm.y == 1.0


def test_zero_dt_does_not_crash() -> None:
    """Same timestamp twice should not divide by zero."""
    cfg = SmoothingConfig(enabled=True, min_cutoff=1.0, beta=0.0, d_cutoff=1.0)
    f = _OneEuro(cfg)
    f.filter(0.5, timestamp_s=1.0)
    # Same timestamp - dt = 0. Must not crash.
    out = f.filter(0.6, timestamp_s=1.0)
    # Should return some sensible value (the last smoothed value).
    assert 0.0 <= out <= 1.0


def main() -> int:
    tests = [
        test_disabled_smoother_is_passthrough,
        test_first_sample_passes_through,
        test_steady_signal_remains_steady,
        test_jitter_around_constant_is_smoothed,
        test_fast_motion_is_responsive_with_beta,
        test_hand_smoother_filters_all_landmarks,
        test_hand_smoother_reset_clears_state,
        test_zero_dt_does_not_crash,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {t.__name__}: {e}")
        except Exception as e:
            failures += 1
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

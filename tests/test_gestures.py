"""Unit tests for the gestures module.

Tests are plain assert statements so they can be run as a script or under
pytest. Run from the project root:
    .venv\\Scripts\\python.exe tests\\test_gestures.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

# Allow running this file directly: python tests/test_gestures.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from composair.gestures import (
    ALL_FINGERS,
    Finger,
    INDEX_TIP,
    MIDDLE_FINGER_MCP,
    PinchDetector,
    PinchEvent,
    Point2D,
    THUMB_TIP,
    VelocityConfig,
    VelocityEstimator,
    WRIST,
    euclidean,
    hand_size,
    normalized_pinch_distance,
    thumb_index_distance,
    thumb_to_finger_distance,
)


_DEFAULT_VEL_CFG = VelocityConfig(
    min_velocity=40,
    max_velocity=120,
    default=90,
    window_ms=150,
    fast_closure_rate=2.0,
)


def _make_hand(
    thumb_index_dist: float,
    hand_size_dist: float = 0.2,
    finger_offsets: dict[Finger, float] | None = None,
) -> list[Point2D]:
    """Build a minimal 21-landmark hand with controllable per-finger gaps.

    Only WRIST, MIDDLE_FINGER_MCP, THUMB_TIP, and the four finger tips need
    real values for the gesture math. By default all four fingertips sit at
    the same x offset (thumb_index_dist) so legacy tests stay valid. Pass
    finger_offsets to give each finger a different x offset, useful for
    testing per-finger detection.
    """
    landmarks = [Point2D(0.0, 0.0)] * 21
    landmarks[WRIST] = Point2D(0.5, 0.9)
    landmarks[MIDDLE_FINGER_MCP] = Point2D(0.5, 0.9 - hand_size_dist)
    landmarks[THUMB_TIP] = Point2D(0.5, 0.5)
    if finger_offsets is None:
        finger_offsets = {f: thumb_index_dist for f in ALL_FINGERS}
    for finger in ALL_FINGERS:
        landmarks[finger.tip_index] = Point2D(0.5 + finger_offsets[finger], 0.5)
    return landmarks


def test_euclidean_basic() -> None:
    assert euclidean(Point2D(0, 0), Point2D(3, 4)) == 5.0
    assert euclidean(Point2D(1, 1), Point2D(1, 1)) == 0.0


def test_hand_size_and_thumb_distance() -> None:
    hand = _make_hand(thumb_index_dist=0.1, hand_size_dist=0.2)
    assert math.isclose(hand_size(hand), 0.2)
    assert math.isclose(thumb_index_distance(hand), 0.1)


def test_normalized_pinch_distance_independent_of_scale() -> None:
    # Same finger gap, different hand scale -> same normalized distance.
    small = _make_hand(thumb_index_dist=0.05, hand_size_dist=0.1)
    large = _make_hand(thumb_index_dist=0.10, hand_size_dist=0.2)
    assert math.isclose(normalized_pinch_distance(small), 0.5)
    assert math.isclose(normalized_pinch_distance(large), 0.5)


def test_normalized_pinch_distance_zero_hand_size_returns_inf() -> None:
    # Degenerate landmarks (e.g. failed tracking) must not crash.
    bad = [Point2D(0.0, 0.0)] * 21
    assert normalized_pinch_distance(bad) == float("inf")


def test_pinch_detector_emits_on_then_off() -> None:
    det = PinchDetector(on_threshold=0.05, off_threshold=0.07)
    assert det.update(0.10) is None      # far apart, no event
    assert det.update(0.04) is PinchEvent.PINCH_ON
    assert det.is_pinched
    assert det.update(0.03) is None      # still pinched, no re-fire
    assert det.update(0.08) is PinchEvent.PINCH_OFF
    assert not det.is_pinched


def test_pinch_detector_hysteresis_prevents_flicker() -> None:
    """Distance bouncing inside the [on, off] band should produce zero events."""
    det = PinchDetector(on_threshold=0.05, off_threshold=0.07)
    det.update(0.03)  # enter pinched state
    events = [det.update(d) for d in (0.06, 0.055, 0.065, 0.06, 0.058)]
    assert all(e is None for e in events), f"unexpected events in band: {events}"
    assert det.is_pinched


def test_pinch_detector_rejects_inverted_thresholds() -> None:
    try:
        PinchDetector(on_threshold=0.07, off_threshold=0.05)
    except ValueError:
        return
    raise AssertionError("PinchDetector should reject on_threshold >= off_threshold")


def test_finger_enum_tip_indices_are_correct() -> None:
    # MediaPipe landmark layout: index 8, middle 12, ring 16, pinky 20.
    assert Finger.INDEX.tip_index == 8
    assert Finger.MIDDLE.tip_index == 12
    assert Finger.RING.tip_index == 16
    assert Finger.PINKY.tip_index == 20


def test_per_finger_distance_isolates_correct_landmark() -> None:
    # Middle finger touches the thumb (offset 0.0); others are 0.5 away.
    hand = _make_hand(
        thumb_index_dist=0.5,
        finger_offsets={
            Finger.INDEX: 0.5,
            Finger.MIDDLE: 0.0,
            Finger.RING: 0.5,
            Finger.PINKY: 0.5,
        },
    )
    assert math.isclose(thumb_to_finger_distance(hand, Finger.MIDDLE), 0.0, abs_tol=1e-9)
    assert math.isclose(thumb_to_finger_distance(hand, Finger.INDEX), 0.5)
    # Normalized middle-pinch should be 0; others should be 0.5/0.2 = 2.5.
    assert math.isclose(normalized_pinch_distance(hand, Finger.MIDDLE), 0.0, abs_tol=1e-9)
    assert math.isclose(normalized_pinch_distance(hand, Finger.RING), 2.5)


def test_four_detectors_fire_independently() -> None:
    """Pinching one finger must not affect the state of any other detector."""
    detectors = {f: PinchDetector(0.05, 0.07) for f in ALL_FINGERS}

    # Only middle finger pinches; the others are far away.
    for finger in ALL_FINGERS:
        d = 0.03 if finger is Finger.MIDDLE else 0.20
        event = detectors[finger].update(d)
        if finger is Finger.MIDDLE:
            assert event is PinchEvent.PINCH_ON, f"{finger} should fire ON"
        else:
            assert event is None, f"{finger} should not fire (got {event})"

    assert detectors[Finger.MIDDLE].is_pinched
    for finger in ALL_FINGERS:
        if finger is not Finger.MIDDLE:
            assert not detectors[finger].is_pinched, f"{finger} wrongly pinched"


def test_velocity_returns_default_with_insufficient_samples() -> None:
    est = VelocityEstimator(_DEFAULT_VEL_CFG)
    assert est.estimate_velocity() == _DEFAULT_VEL_CFG.default
    est.add_sample(0.0, 0.5)
    assert est.estimate_velocity() == _DEFAULT_VEL_CFG.default


def test_velocity_min_when_distance_is_increasing() -> None:
    """Opening the pinch (distance going up) should not produce a loud note."""
    est = VelocityEstimator(_DEFAULT_VEL_CFG)
    est.add_sample(0.00, 0.10)
    est.add_sample(0.05, 0.15)
    est.add_sample(0.10, 0.20)
    assert est.estimate_velocity() == _DEFAULT_VEL_CFG.min_velocity


def test_velocity_max_when_closing_fast() -> None:
    """A closure rate >= fast_closure_rate should saturate at max_velocity."""
    est = VelocityEstimator(_DEFAULT_VEL_CFG)
    # Close 0.5 normalized units in 0.1 s = 5 units/sec, well above fast_closure_rate=2.
    est.add_sample(0.00, 0.50)
    est.add_sample(0.10, 0.00)
    assert est.estimate_velocity() == _DEFAULT_VEL_CFG.max_velocity


def test_velocity_scales_linearly_in_between() -> None:
    """A closure rate of exactly fast_closure_rate/2 should produce the midpoint."""
    est = VelocityEstimator(_DEFAULT_VEL_CFG)
    # 0.1 unit / 0.1 s = 1 unit/sec = half of fast_closure_rate=2.
    est.add_sample(0.00, 0.20)
    est.add_sample(0.10, 0.10)
    midpoint = (_DEFAULT_VEL_CFG.min_velocity + _DEFAULT_VEL_CFG.max_velocity) // 2
    velocity = est.estimate_velocity()
    # Allow +/- 1 for integer rounding.
    assert abs(velocity - midpoint) <= 1, f"expected near {midpoint}, got {velocity}"


def test_velocity_evicts_old_samples_outside_window() -> None:
    """Samples older than window_ms must not contribute to the estimate."""
    est = VelocityEstimator(_DEFAULT_VEL_CFG)
    # Old slow sample, should be evicted.
    est.add_sample(0.0, 0.50)
    # Fast close inside the recent 0.1s.
    est.add_sample(0.30, 0.40)
    est.add_sample(0.40, 0.10)
    velocity = est.estimate_velocity()
    # Only the last two samples should remain (window is 150ms; 0.4 - 0.0 = 0.4s evicted 0.0).
    # Closure 0.3 over 0.1s = 3.0 unit/s > fast_closure_rate, so max.
    assert velocity == _DEFAULT_VEL_CFG.max_velocity


def test_velocity_rejects_bad_config() -> None:
    cases = [
        VelocityConfig(0, 120, 90, 150, 2.0),     # min < 1
        VelocityConfig(40, 200, 90, 150, 2.0),    # max > 127
        VelocityConfig(120, 40, 90, 150, 2.0),    # min > max
        VelocityConfig(40, 120, 90, 0, 2.0),      # window_ms <= 0
        VelocityConfig(40, 120, 90, 150, 0),      # fast_closure_rate <= 0
        VelocityConfig(40, 120, 0, 150, 2.0),     # default out of range
    ]
    for cfg in cases:
        try:
            VelocityEstimator(cfg)
        except ValueError:
            continue
        raise AssertionError(f"VelocityEstimator should have rejected: {cfg}")


def main() -> int:
    tests = [
        test_euclidean_basic,
        test_hand_size_and_thumb_distance,
        test_normalized_pinch_distance_independent_of_scale,
        test_normalized_pinch_distance_zero_hand_size_returns_inf,
        test_pinch_detector_emits_on_then_off,
        test_pinch_detector_hysteresis_prevents_flicker,
        test_pinch_detector_rejects_inverted_thresholds,
        test_finger_enum_tip_indices_are_correct,
        test_per_finger_distance_isolates_correct_landmark,
        test_four_detectors_fire_independently,
        test_velocity_returns_default_with_insufficient_samples,
        test_velocity_min_when_distance_is_increasing,
        test_velocity_max_when_closing_fast,
        test_velocity_scales_linearly_in_between,
        test_velocity_evicts_old_samples_outside_window,
        test_velocity_rejects_bad_config,
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

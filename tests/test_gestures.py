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
    INDEX_TIP,
    MIDDLE_FINGER_MCP,
    PinchDetector,
    PinchEvent,
    Point2D,
    THUMB_TIP,
    WRIST,
    euclidean,
    hand_size,
    normalized_pinch_distance,
    thumb_index_distance,
)


def _make_hand(thumb_index_dist: float, hand_size_dist: float = 0.2) -> list[Point2D]:
    """Build a minimal 21-landmark hand with controllable thumb-index gap.

    Only WRIST, MIDDLE_FINGER_MCP, THUMB_TIP, INDEX_TIP need real values
    for the gesture math; the rest are filled with zeros for indexing safety.
    """
    landmarks = [Point2D(0.0, 0.0)] * 21
    landmarks[WRIST] = Point2D(0.5, 0.9)
    landmarks[MIDDLE_FINGER_MCP] = Point2D(0.5, 0.9 - hand_size_dist)
    landmarks[THUMB_TIP] = Point2D(0.5, 0.5)
    landmarks[INDEX_TIP] = Point2D(0.5 + thumb_index_dist, 0.5)
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


def main() -> int:
    tests = [
        test_euclidean_basic,
        test_hand_size_and_thumb_distance,
        test_normalized_pinch_distance_independent_of_scale,
        test_normalized_pinch_distance_zero_hand_size_returns_inf,
        test_pinch_detector_emits_on_then_off,
        test_pinch_detector_hysteresis_prevents_flicker,
        test_pinch_detector_rejects_inverted_thresholds,
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

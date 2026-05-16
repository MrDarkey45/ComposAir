"""Unit tests for ModulationMapper.

Run from the project root:
    .venv\\Scripts\\python.exe tests\\test_modulation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from composair.modulation import ModulationConfig, ModulationMapper


def _cfg(
    cc=74, smoothing=0.0, deadzone=0, interval_ms=30,
) -> ModulationConfig:
    return ModulationConfig(
        cc_number=cc, smoothing=smoothing,
        deadzone=deadzone, update_interval_ms=interval_ms,
    )


def test_hand_at_top_produces_high_cc() -> None:
    m = ModulationMapper(_cfg())
    # y = 0 means top of screen; user has raised the hand high.
    assert m.compute_value(0.0) == 127


def test_hand_at_bottom_produces_low_cc() -> None:
    m = ModulationMapper(_cfg())
    assert m.compute_value(1.0) == 0


def test_hand_in_middle_produces_midpoint_cc() -> None:
    m = ModulationMapper(_cfg())
    val = m.compute_value(0.5)
    # 1.0 - 0.5 = 0.5 -> 63 or 64.
    assert val in (63, 64)


def test_y_out_of_range_is_clamped() -> None:
    m = ModulationMapper(_cfg())
    assert m.compute_value(-0.5) == 127
    assert m.compute_value(1.5) == 0


def test_smoothing_dampens_jumps() -> None:
    """With strong smoothing the value should not jump to the target in one step."""
    m = ModulationMapper(_cfg(smoothing=0.8))
    m.compute_value(1.0)            # start at bottom -> 0
    val_after_jump = m.compute_value(0.0)  # try to jump to top
    # Without smoothing this would be 127; with smoothing 0.8 the new y is
    # 0.2 * 0 + 0.8 * 1.0 = 0.8, so cc = (1 - 0.8) * 127 = ~25.
    assert val_after_jump < 50, f"expected damped value, got {val_after_jump}"


def test_deadzone_blocks_tiny_deltas() -> None:
    m = ModulationMapper(_cfg(deadzone=5))
    val = m.compute_value(0.5)
    m.mark_sent(val)
    # A second sample producing val+1 should NOT pass the deadzone.
    near = m.compute_value(0.495)
    assert abs(near - val) < 5, "test setup: deltas should be small here"
    assert not m.should_emit(near)


def test_deadzone_allows_large_deltas() -> None:
    m = ModulationMapper(_cfg(deadzone=5))
    val = m.compute_value(0.5)
    m.mark_sent(val)
    # Move the hand to the top - big change.
    far = m.compute_value(0.0)
    assert m.should_emit(far)


def test_first_emit_always_allowed() -> None:
    m = ModulationMapper(_cfg(deadzone=50))
    # No prior send: should_emit must return True regardless of deadzone.
    assert m.should_emit(0)
    assert m.should_emit(127)


def test_reset_clears_state() -> None:
    m = ModulationMapper(_cfg(smoothing=0.5))
    m.compute_value(1.0)
    m.mark_sent(0)
    m.reset()
    assert m.last_sent is None
    # First post-reset value should not be affected by previous smoothing.
    val = m.compute_value(0.0)
    assert val == 127


def test_rejects_bad_config() -> None:
    cases = [
        _cfg(cc=-1),
        _cfg(cc=200),
        _cfg(smoothing=1.0),
        _cfg(smoothing=-0.1),
        _cfg(deadzone=-1),
        _cfg(interval_ms=0),
    ]
    for cfg in cases:
        try:
            ModulationMapper(cfg)
        except ValueError:
            continue
        raise AssertionError(f"ModulationMapper should have rejected: {cfg}")


def main() -> int:
    tests = [
        test_hand_at_top_produces_high_cc,
        test_hand_at_bottom_produces_low_cc,
        test_hand_in_middle_produces_midpoint_cc,
        test_y_out_of_range_is_clamped,
        test_smoothing_dampens_jumps,
        test_deadzone_blocks_tiny_deltas,
        test_deadzone_allows_large_deltas,
        test_first_emit_always_allowed,
        test_reset_clears_state,
        test_rejects_bad_config,
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

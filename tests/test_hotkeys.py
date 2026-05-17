"""Unit tests for the hotkey resolver.

Run from the project root:
    .venv\\Scripts\\python.exe tests\\test_hotkeys.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from composair.hotkeys import (
    KEY_CYCLE,
    KEY_HOTKEYS,
    SCALE_CYCLE,
    SCALE_HOTKEYS,
    SCALE_PAIRS,
    SCALE_TOGGLE_KEYS,
    ActionType,
    cycle_key,
    cycle_scale,
    resolve,
    resolve_scale_pair_toggle,
)
from composair.scales import KEY_OFFSETS, SCALES


def test_q_resolves_to_quit() -> None:
    assert resolve(ord("q")).type is ActionType.QUIT


def test_r_resolves_to_record_toggle() -> None:
    assert resolve(ord("r")).type is ActionType.RECORD_TOGGLE


def test_brackets_resolve_to_instrument_prev_next() -> None:
    assert resolve(ord("[")).type is ActionType.INSTRUMENT_PREV
    assert resolve(ord("]")).type is ActionType.INSTRUMENT_NEXT


def test_s_resolves_to_open_settings() -> None:
    assert resolve(ord("s")).type is ActionType.OPEN_SETTINGS


def test_digits_1_to_7_map_to_keys_c_through_b() -> None:
    expected = {"1": "C", "2": "D", "3": "E", "4": "F", "5": "G", "6": "A", "7": "B"}
    for digit, key_name in expected.items():
        action = resolve(ord(digit))
        assert action.type is ActionType.SET_KEY, f"{digit} should be SET_KEY"
        assert action.payload == key_name, f"{digit} should give {key_name}"


def test_all_key_hotkey_payloads_are_real_keys() -> None:
    """Every key the hotkey table can emit must be a key scales.py accepts."""
    for hotkey_code, key_letter in KEY_HOTKEYS.items():
        assert key_letter in KEY_OFFSETS, (
            f"hotkey {chr(hotkey_code)} -> {key_letter} not in scales.KEY_OFFSETS"
        )


def test_direct_scale_letter_keys() -> None:
    """h and d are direct scale selections; lowercase, no toggle."""
    h_action = resolve(ord("h"))
    assert h_action.type is ActionType.SET_SCALE
    assert h_action.payload == "harmonic_minor"
    d_action = resolve(ord("d"))
    assert d_action.type is ActionType.SET_SCALE
    assert d_action.payload == "dorian"


def test_all_scale_hotkey_payloads_are_real_scales() -> None:
    """Every direct scale name in the hotkey table must be in scales.SCALES."""
    for hotkey_code, scale_name in SCALE_HOTKEYS.items():
        assert scale_name in SCALES, (
            f"hotkey {chr(hotkey_code)} -> {scale_name} not in scales.SCALES"
        )


def test_m_resolves_to_toggle_major_minor() -> None:
    action = resolve(ord("m"))
    assert action.type is ActionType.TOGGLE_SCALE_PAIR
    assert action.payload == "major_minor"


def test_p_resolves_to_toggle_pentatonic() -> None:
    action = resolve(ord("p"))
    assert action.type is ActionType.TOGGLE_SCALE_PAIR
    assert action.payload == "pentatonic"


def test_uppercase_M_and_P_are_not_recognized() -> None:
    # Toggle keys are lowercase only; uppercase variants fall through to NONE.
    assert resolve(ord("M")).type is ActionType.NONE
    assert resolve(ord("P")).type is ActionType.NONE


def test_all_scale_toggle_pair_targets_are_real_scales() -> None:
    """Both sides of every pair must be valid scale names."""
    for pair_id, (primary, secondary) in SCALE_PAIRS.items():
        assert primary in SCALES, f"pair {pair_id} primary {primary} unknown"
        assert secondary in SCALES, f"pair {pair_id} secondary {secondary} unknown"


def test_resolve_pair_toggle_flips_within_pair() -> None:
    assert resolve_scale_pair_toggle("major_minor", "major") == "natural_minor"
    assert resolve_scale_pair_toggle("major_minor", "natural_minor") == "major"
    assert resolve_scale_pair_toggle("pentatonic", "major_pentatonic") == "minor_pentatonic"
    assert resolve_scale_pair_toggle("pentatonic", "minor_pentatonic") == "major_pentatonic"


def test_resolve_pair_toggle_from_unrelated_scale_jumps_to_primary() -> None:
    # Currently on dorian; pressing m should jump to major (the primary of major_minor).
    assert resolve_scale_pair_toggle("major_minor", "dorian") == "major"
    assert resolve_scale_pair_toggle("pentatonic", "harmonic_minor") == "major_pentatonic"


def test_resolve_pair_toggle_rejects_unknown_pair() -> None:
    try:
        resolve_scale_pair_toggle("not_a_pair", "major")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unknown pair id")


def test_cycle_key_advances_chromatically() -> None:
    assert cycle_key("C", +1) == "C#"
    assert cycle_key("C#", +1) == "D"
    assert cycle_key("B", +1) == "C"  # wraps


def test_cycle_key_reverses() -> None:
    assert cycle_key("C", -1) == "B"  # wraps
    assert cycle_key("D", -1) == "C#"


def test_cycle_key_falls_back_for_unknown_key() -> None:
    assert cycle_key("X", +1) == KEY_CYCLE[0]


def test_cycle_scale_advances_and_wraps() -> None:
    # major -> major_pentatonic per SCALE_CYCLE order
    assert cycle_scale("major", +1) == "major_pentatonic"
    # Last entry wraps back to first.
    assert cycle_scale(SCALE_CYCLE[-1], +1) == SCALE_CYCLE[0]


def test_cycle_scale_reverses_and_wraps() -> None:
    assert cycle_scale(SCALE_CYCLE[0], -1) == SCALE_CYCLE[-1]
    assert cycle_scale("major_pentatonic", -1) == "major"


def test_cycle_scale_falls_back_for_unknown_scale() -> None:
    assert cycle_scale("not_a_scale", +1) == SCALE_CYCLE[0]


def test_all_cycle_keys_are_in_KEY_OFFSETS() -> None:
    for k in KEY_CYCLE:
        assert k in KEY_OFFSETS, f"cycle key {k} not in scales.KEY_OFFSETS"


def test_all_cycle_scales_are_in_SCALES() -> None:
    for s in SCALE_CYCLE:
        assert s in SCALES, f"cycle scale {s} not in scales.SCALES"


def test_all_toggle_keys_map_to_valid_pairs() -> None:
    for code, pair_id in SCALE_TOGGLE_KEYS.items():
        assert pair_id in SCALE_PAIRS, (
            f"toggle key {chr(code)} -> {pair_id} has no pair definition"
        )


def test_unknown_key_is_none() -> None:
    for ch in ("a", "z", "0", "8", " ", "\t"):
        action = resolve(ord(ch))
        assert action.type is ActionType.NONE, f"'{ch}' should be NONE, got {action.type}"


def test_waitkey_no_key_value() -> None:
    """cv2.waitKey returns 255 (after & 0xFF) when no key was pressed."""
    assert resolve(255).type is ActionType.NONE


def main() -> int:
    tests = [
        test_q_resolves_to_quit,
        test_r_resolves_to_record_toggle,
        test_brackets_resolve_to_instrument_prev_next,
        test_s_resolves_to_open_settings,
        test_digits_1_to_7_map_to_keys_c_through_b,
        test_all_key_hotkey_payloads_are_real_keys,
        test_direct_scale_letter_keys,
        test_all_scale_hotkey_payloads_are_real_scales,
        test_m_resolves_to_toggle_major_minor,
        test_p_resolves_to_toggle_pentatonic,
        test_uppercase_M_and_P_are_not_recognized,
        test_all_scale_toggle_pair_targets_are_real_scales,
        test_resolve_pair_toggle_flips_within_pair,
        test_resolve_pair_toggle_from_unrelated_scale_jumps_to_primary,
        test_resolve_pair_toggle_rejects_unknown_pair,
        test_cycle_key_advances_chromatically,
        test_cycle_key_reverses,
        test_cycle_key_falls_back_for_unknown_key,
        test_cycle_scale_advances_and_wraps,
        test_cycle_scale_reverses_and_wraps,
        test_cycle_scale_falls_back_for_unknown_scale,
        test_all_cycle_keys_are_in_KEY_OFFSETS,
        test_all_cycle_scales_are_in_SCALES,
        test_all_toggle_keys_map_to_valid_pairs,
        test_unknown_key_is_none,
        test_waitkey_no_key_value,
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

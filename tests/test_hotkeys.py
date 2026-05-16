"""Unit tests for the hotkey resolver.

Run from the project root:
    .venv\\Scripts\\python.exe tests\\test_hotkeys.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from composair.hotkeys import (
    KEY_HOTKEYS,
    SCALE_HOTKEYS,
    ActionType,
    resolve,
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


def test_scale_letter_keys() -> None:
    cases = {
        "M": "major",
        "n": "natural_minor",
        "h": "harmonic_minor",
        "d": "dorian",
        "P": "major_pentatonic",
        "p": "minor_pentatonic",
    }
    for ch, expected_scale in cases.items():
        action = resolve(ord(ch))
        assert action.type is ActionType.SET_SCALE, f"'{ch}' should be SET_SCALE"
        assert action.payload == expected_scale, (
            f"'{ch}' should give {expected_scale}, got {action.payload}"
        )


def test_all_scale_hotkey_payloads_are_real_scales() -> None:
    """Every scale name the hotkey table can emit must be in scales.SCALES."""
    for hotkey_code, scale_name in SCALE_HOTKEYS.items():
        assert scale_name in SCALES, (
            f"hotkey {chr(hotkey_code)} -> {scale_name} not in scales.SCALES"
        )


def test_scale_case_distinguishes_major_minor_pentatonic() -> None:
    """The case-sensitivity that disambiguates pent+ and pent- must be real."""
    assert resolve(ord("P")).payload == "major_pentatonic"
    assert resolve(ord("p")).payload == "minor_pentatonic"
    assert resolve(ord("M")).payload == "major"
    assert resolve(ord("n")).payload == "natural_minor"


def test_unknown_key_is_none() -> None:
    # Random keys that have no hotkey mapping must return NONE.
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
        test_scale_letter_keys,
        test_all_scale_hotkey_payloads_are_real_scales,
        test_scale_case_distinguishes_major_minor_pentatonic,
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

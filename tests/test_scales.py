"""Unit tests for scales and mapping (octave bands).

Run from the project root:
    .venv\\Scripts\\python.exe tests\\test_scales.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from composair.gestures import Finger
from composair.mapping import (
    BandSelectorConfig,
    OctaveBandSelector,
    resolve_midi_note,
)
from composair.scales import ScaleSpec, scale_degree_to_midi


# --- Scale theory --------------------------------------------------------

def test_c_major_basic_degrees() -> None:
    spec = ScaleSpec(key="C", scale_name="major")
    # Octave 4: degree 1 = C4 = MIDI 60.
    assert scale_degree_to_midi(spec, 1, 4) == 60
    assert scale_degree_to_midi(spec, 2, 4) == 62  # D4
    assert scale_degree_to_midi(spec, 3, 4) == 64  # E4
    assert scale_degree_to_midi(spec, 5, 4) == 67  # G4
    assert scale_degree_to_midi(spec, 7, 4) == 71  # B4


def test_degree_wraps_into_next_octave() -> None:
    spec = ScaleSpec(key="C", scale_name="major")
    # Degree 8 is the octave above degree 1.
    assert scale_degree_to_midi(spec, 8, 4) == 72   # C5
    assert scale_degree_to_midi(spec, 15, 4) == 84  # C6


def test_pentatonic_has_five_degrees_per_octave() -> None:
    spec = ScaleSpec(key="C", scale_name="major_pentatonic")
    # Major pentatonic: C, D, E, G, A. Degree 6 should be next-octave C.
    assert scale_degree_to_midi(spec, 1, 4) == 60   # C4
    assert scale_degree_to_midi(spec, 2, 4) == 62   # D4
    assert scale_degree_to_midi(spec, 3, 4) == 64   # E4
    assert scale_degree_to_midi(spec, 4, 4) == 67   # G4
    assert scale_degree_to_midi(spec, 5, 4) == 69   # A4
    assert scale_degree_to_midi(spec, 6, 4) == 72   # C5 (wrap)


def test_key_transposition() -> None:
    g_major = ScaleSpec(key="G", scale_name="major")
    # Degree 1 of G major at octave 4 = G4 = MIDI 67.
    assert scale_degree_to_midi(g_major, 1, 4) == 67
    # Degree 3 of G major = B4 = MIDI 71.
    assert scale_degree_to_midi(g_major, 3, 4) == 71


def test_natural_minor_third_is_flatted() -> None:
    c_minor = ScaleSpec(key="C", scale_name="natural_minor")
    # Natural minor 3rd is Eb (MIDI 63), not E (64).
    assert scale_degree_to_midi(c_minor, 3, 4) == 63


def test_degree_below_one_raises() -> None:
    spec = ScaleSpec(key="C", scale_name="major")
    try:
        scale_degree_to_midi(spec, 0, 4)
    except ValueError:
        return
    raise AssertionError("expected ValueError for degree=0")


def test_out_of_midi_range_raises() -> None:
    spec = ScaleSpec(key="C", scale_name="major")
    # Octave 12 pushes us above MIDI 127.
    try:
        scale_degree_to_midi(spec, 8, 12)
    except ValueError:
        return
    raise AssertionError("expected ValueError for MIDI out of range")


# --- Octave band selector -----------------------------------------------

def test_band_selector_starts_in_middle() -> None:
    sel = OctaveBandSelector(BandSelectorConfig(num_bands=3, base_octave=4, hysteresis=0.02))
    assert sel.current_band == 1


def test_band_selector_moves_with_hand_position() -> None:
    sel = OctaveBandSelector(BandSelectorConfig(num_bands=3, base_octave=4, hysteresis=0.0))
    # Hand at top of screen (low Y) -> top band.
    assert sel.update(0.1) == 2
    # Hand at bottom -> bottom band.
    assert sel.update(0.9) == 0
    # Middle.
    assert sel.update(0.5) == 1


def test_band_selector_hysteresis_holds_state_inside_band_gap() -> None:
    sel = OctaveBandSelector(BandSelectorConfig(num_bands=3, base_octave=4, hysteresis=0.05))
    sel.update(0.1)  # firmly in top band (2)
    # Right at the boundary between band 2 and band 1 (boundary at Y=1/3 = 0.333).
    # Without hysteresis we'd flip; with 0.05 we should hold.
    assert sel.update(0.34) == 2, "should still be band 2"
    # Now cross noticeably past the boundary into band 1.
    assert sel.update(0.45) == 1, "should now be band 1"


def test_band_selector_octave_for_band() -> None:
    sel = OctaveBandSelector(BandSelectorConfig(num_bands=3, base_octave=4, hysteresis=0.02))
    assert sel.octave_for_band(0) == 4
    assert sel.octave_for_band(1) == 5
    assert sel.octave_for_band(2) == 6


def test_resolve_midi_note_integration() -> None:
    spec = ScaleSpec(key="C", scale_name="major")
    finger_degrees = {Finger.INDEX: 1, Finger.MIDDLE: 3, Finger.RING: 5, Finger.PINKY: 7}
    sel = OctaveBandSelector(BandSelectorConfig(num_bands=3, base_octave=4, hysteresis=0.02))
    # Middle band = octave 5. Index = degree 1 = C5 = MIDI 72.
    assert resolve_midi_note(spec, finger_degrees, Finger.INDEX, 1, sel) == 72
    # Ring = degree 5 = G5 = MIDI 79.
    assert resolve_midi_note(spec, finger_degrees, Finger.RING, 1, sel) == 79


def main() -> int:
    tests = [
        test_c_major_basic_degrees,
        test_degree_wraps_into_next_octave,
        test_pentatonic_has_five_degrees_per_octave,
        test_key_transposition,
        test_natural_minor_third_is_flatted,
        test_degree_below_one_raises,
        test_out_of_midi_range_raises,
        test_band_selector_starts_in_middle,
        test_band_selector_moves_with_hand_position,
        test_band_selector_hysteresis_holds_state_inside_band_gap,
        test_band_selector_octave_for_band,
        test_resolve_midi_note_integration,
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

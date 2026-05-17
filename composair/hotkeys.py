"""Keyboard hotkey table for live key / scale changes.

Resolves a raw character code from cv2.waitKey to a HotkeyAction describing
what should change. main.py is then responsible for applying the change
to the live state (and the recorder, when appropriate).

Hotkey ASCII conventions:
- '1'..'7' choose a musical key (C, D, E, F, G, A, B).
- Letter keys choose a scale. No Shift required:
  - 'm' toggles major <-> natural minor
  - 'p' toggles major pentatonic <-> minor pentatonic
  - 'h' selects harmonic minor
  - 'd' selects dorian
- Toggle actions need to know the current scale to decide which side
  of the pair to flip to, so they carry a TOGGLE_SCALE_PAIR action whose
  payload is the pair identifier; main.py resolves the actual scale.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class ActionType(Enum):
    """Discriminator for HotkeyAction.

    Payload-carrying actions:
    - SET_KEY: payload is a key name like "C", "F#"
    - SET_SCALE: payload is a scale name like "major"
    - TOGGLE_SCALE_PAIR: payload is a pair id ("major_minor" or "pentatonic")
    """

    NONE = auto()
    QUIT = auto()
    RECORD_TOGGLE = auto()
    INSTRUMENT_PREV = auto()
    INSTRUMENT_NEXT = auto()
    SET_KEY = auto()
    SET_SCALE = auto()
    TOGGLE_SCALE_PAIR = auto()
    OPEN_SETTINGS = auto()


@dataclass(frozen=True)
class HotkeyAction:
    """What main.py should do in response to a keypress."""

    type: ActionType
    payload: str = ""


# 1..7 -> musical key letters per the README hotkey table.
KEY_HOTKEYS: dict[int, str] = {
    ord("1"): "C",
    ord("2"): "D",
    ord("3"): "E",
    ord("4"): "F",
    ord("5"): "G",
    ord("6"): "A",
    ord("7"): "B",
}

# Direct scale selections. Lowercase, no Shift required.
SCALE_HOTKEYS: dict[int, str] = {
    ord("h"): "harmonic_minor",
    ord("d"): "dorian",
}

# Pair-toggle scale keys. Pressing flips between the two scales in the pair;
# pressing from any other scale jumps to the pair's primary (first entry).
SCALE_TOGGLE_KEYS: dict[int, str] = {
    ord("m"): "major_minor",
    ord("p"): "pentatonic",
}

# Pair id -> (primary, secondary). resolve_scale_pair_toggle uses this.
SCALE_PAIRS: dict[str, tuple[str, str]] = {
    "major_minor": ("major", "natural_minor"),
    "pentatonic": ("major_pentatonic", "minor_pentatonic"),
}

# Ordered key cycle for left-hand-pinch transport. Chromatic, starts at C.
KEY_CYCLE: tuple[str, ...] = (
    "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
)

# Ordered scale cycle for left-hand-pinch transport. Brightest to darkest.
SCALE_CYCLE: tuple[str, ...] = (
    "major",
    "major_pentatonic",
    "dorian",
    "minor_pentatonic",
    "natural_minor",
    "harmonic_minor",
)


def resolve(key_code: int) -> HotkeyAction:
    """Map a cv2.waitKey return value (already &0xFF) to a HotkeyAction.

    Returns ActionType.NONE for keys we do not handle, so callers can
    check `action.type is ActionType.NONE` to ignore them cleanly.
    """
    if key_code == ord("q"):
        return HotkeyAction(ActionType.QUIT)
    if key_code == ord("r"):
        return HotkeyAction(ActionType.RECORD_TOGGLE)
    if key_code == ord("s"):
        return HotkeyAction(ActionType.OPEN_SETTINGS)
    if key_code == ord("["):
        return HotkeyAction(ActionType.INSTRUMENT_PREV)
    if key_code == ord("]"):
        return HotkeyAction(ActionType.INSTRUMENT_NEXT)
    if key_code in KEY_HOTKEYS:
        return HotkeyAction(ActionType.SET_KEY, KEY_HOTKEYS[key_code])
    if key_code in SCALE_HOTKEYS:
        return HotkeyAction(ActionType.SET_SCALE, SCALE_HOTKEYS[key_code])
    if key_code in SCALE_TOGGLE_KEYS:
        return HotkeyAction(ActionType.TOGGLE_SCALE_PAIR, SCALE_TOGGLE_KEYS[key_code])
    return HotkeyAction(ActionType.NONE)


def resolve_scale_pair_toggle(pair_id: str, current_scale: str) -> str:
    """Given the toggle's pair id and the current scale, return the other side.

    If current_scale is not in the pair, returns the pair's primary so that
    pressing the toggle from an unrelated scale jumps cleanly into the pair.
    """
    if pair_id not in SCALE_PAIRS:
        raise ValueError(f"unknown scale pair '{pair_id}'")
    primary, secondary = SCALE_PAIRS[pair_id]
    if current_scale == primary:
        return secondary
    if current_scale == secondary:
        return primary
    return primary


def cycle_key(current_key: str, step: int) -> str:
    """Return the next/previous key in the chromatic cycle (wraps both ends).

    step=+1 advances; step=-1 goes back. Used by left-hand transport pinches.
    """
    try:
        idx = KEY_CYCLE.index(current_key)
    except ValueError:
        return KEY_CYCLE[0]
    return KEY_CYCLE[(idx + step) % len(KEY_CYCLE)]


def cycle_scale(current_scale: str, step: int) -> str:
    """Return the next/previous scale in the brightness-ordered cycle."""
    try:
        idx = SCALE_CYCLE.index(current_scale)
    except ValueError:
        return SCALE_CYCLE[0]
    return SCALE_CYCLE[(idx + step) % len(SCALE_CYCLE)]

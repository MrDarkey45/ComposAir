"""Keyboard hotkey table for live key / scale changes.

Resolves a raw character code from cv2.waitKey to a HotkeyAction describing
what should change. main.py is then responsible for applying the change
to the live state (and the recorder, when appropriate).

Hotkey ASCII conventions:
- '1'..'7' choose a musical key (C, D, E, F, G, A, B).
- A small set of letter keys choose a scale. Case-sensitive because
  major vs minor uses M / n, and major-pentatonic vs minor-pentatonic
  uses P / p, matching the project's documented hotkey conventions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class ActionType(Enum):
    """Discriminator for HotkeyAction.

    NOTE / SCALE actions carry a string payload; QUIT / RECORD_TOGGLE /
    INSTRUMENT_PREV / INSTRUMENT_NEXT have no payload.
    """

    NONE = auto()
    QUIT = auto()
    RECORD_TOGGLE = auto()
    INSTRUMENT_PREV = auto()
    INSTRUMENT_NEXT = auto()
    SET_KEY = auto()
    SET_SCALE = auto()


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

# Letter -> scale name. Case-sensitive (uppercase M and P vs lowercase n
# and p) because two scale pairs share initials and the spec uses case
# to disambiguate.
SCALE_HOTKEYS: dict[int, str] = {
    ord("M"): "major",
    ord("n"): "natural_minor",
    ord("h"): "harmonic_minor",
    ord("d"): "dorian",
    ord("P"): "major_pentatonic",
    ord("p"): "minor_pentatonic",
}


def resolve(key_code: int) -> HotkeyAction:
    """Map a cv2.waitKey return value (already &0xFF) to a HotkeyAction.

    Returns ActionType.NONE for keys we do not handle, so callers can
    check `action.type is ActionType.NONE` to ignore them cleanly.
    """
    if key_code == ord("q"):
        return HotkeyAction(ActionType.QUIT)
    if key_code == ord("r"):
        return HotkeyAction(ActionType.RECORD_TOGGLE)
    if key_code == ord("["):
        return HotkeyAction(ActionType.INSTRUMENT_PREV)
    if key_code == ord("]"):
        return HotkeyAction(ActionType.INSTRUMENT_NEXT)
    if key_code in KEY_HOTKEYS:
        return HotkeyAction(ActionType.SET_KEY, KEY_HOTKEYS[key_code])
    if key_code in SCALE_HOTKEYS:
        return HotkeyAction(ActionType.SET_SCALE, SCALE_HOTKEYS[key_code])
    return HotkeyAction(ActionType.NONE)

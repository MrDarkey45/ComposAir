"""Smoke test: load the SoundFont, play middle C for ~1 second, then exit.

Run from the project root:
    .venv\\Scripts\\python.exe tests\\test_synth.py

You should HEAR a piano note. If not, check the audio_driver / output device.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import fluidsynth

SOUNDFONT = Path(__file__).resolve().parent.parent / "soundfonts" / "GeneralUser-GS.sf2"
AUDIO_DRIVER = "dsound"  # DirectSound - universal on Windows
GM_PROGRAM = 0           # 0 = Acoustic Grand Piano
MIDI_NOTE = 60           # middle C
VELOCITY = 100
HOLD_SECONDS = 1.0


def main() -> int:
    if not SOUNDFONT.exists():
        print(f"ERROR: soundfont not found at {SOUNDFONT}", file=sys.stderr)
        return 1

    print(f"Loading FluidSynth (driver={AUDIO_DRIVER})...")
    fs = fluidsynth.Synth()
    fs.start(driver=AUDIO_DRIVER)

    print(f"Loading soundfont: {SOUNDFONT}")
    sfid = fs.sfload(str(SOUNDFONT))
    if sfid == -1:
        print("ERROR: sfload returned -1 (soundfont failed to load)", file=sys.stderr)
        fs.delete()
        return 1

    fs.program_select(0, sfid, 0, GM_PROGRAM)
    print(f"Playing MIDI note {MIDI_NOTE} (middle C) at velocity {VELOCITY} for {HOLD_SECONDS}s...")
    fs.noteon(0, MIDI_NOTE, VELOCITY)
    time.sleep(HOLD_SECONDS)
    fs.noteoff(0, MIDI_NOTE)
    time.sleep(0.5)  # let the release tail finish

    fs.delete()
    print("OK - if you heard a piano note, the synth chain works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

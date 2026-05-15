"""Thin wrapper around pyFluidSynth.

Owns the FluidSynth lifecycle and exposes a small, intentional API:
note_on, note_off, close. Future phases add program_change, control_change.
"""

from __future__ import annotations

import logging
from pathlib import Path

import fluidsynth

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = 0
DEFAULT_BANK = 0
MAX_GM_PROGRAM = 127  # General MIDI defines programs 0-127


class Synth:
    """FluidSynth wrapper bound to a single SoundFont and channel."""

    def __init__(
        self,
        soundfont: Path,
        instrument: int,
        audio_driver: str = "dsound",
        sample_rate: int = 44100,
    ) -> None:
        if not soundfont.exists():
            raise FileNotFoundError(f"SoundFont not found: {soundfont}")

        logger.info("Starting FluidSynth (driver=%s, rate=%d)", audio_driver, sample_rate)
        self._fs = fluidsynth.Synth(samplerate=float(sample_rate))
        self._fs.start(driver=audio_driver)

        logger.info("Loading SoundFont: %s", soundfont)
        self._sfid = self._fs.sfload(str(soundfont))
        if self._sfid == -1:
            raise RuntimeError(f"FluidSynth failed to load SoundFont: {soundfont}")

        self._fs.program_select(DEFAULT_CHANNEL, self._sfid, DEFAULT_BANK, instrument)
        self._program = instrument
        logger.info("Selected instrument %d on channel %d", instrument, DEFAULT_CHANNEL)

    @property
    def program(self) -> int:
        """Current General MIDI program number (0-127)."""
        return self._program

    def change_instrument(self, program: int) -> None:
        """Switch to a different GM instrument. Wraps program into 0-127.

        Held notes are not automatically released; FluidSynth will let any
        sounding voices ring out under their original program while new
        notes use the new program. Most users want a clean handoff, but
        forcibly cutting notes here would feel jarring.
        """
        program = program % (MAX_GM_PROGRAM + 1)
        self._fs.program_select(DEFAULT_CHANNEL, self._sfid, DEFAULT_BANK, program)
        self._program = program
        logger.info("Switched to instrument %d", program)

    def note_on(self, midi_note: int, velocity: int = 100) -> None:
        """Trigger a MIDI note. Velocity 1-127."""
        self._fs.noteon(DEFAULT_CHANNEL, midi_note, velocity)

    def note_off(self, midi_note: int) -> None:
        """Release a MIDI note."""
        self._fs.noteoff(DEFAULT_CHANNEL, midi_note)

    def close(self) -> None:
        """Shut down FluidSynth and release the audio device."""
        logger.info("Shutting down FluidSynth")
        self._fs.delete()

    def __enter__(self) -> "Synth":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

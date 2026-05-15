"""MIDI file recording.

A MidiRecorder captures note-on / note-off / program-change events with
wall-clock timestamps and writes a Standard MIDI File (SMF type 0) on
stop. Output files are DAW-ready: drag them into FL Studio, Reaper,
Ableton, GarageBand, etc.

Channel and tick math:
- All events go on MIDI channel 0 (matches the synth wrapper).
- The file uses 480 ticks per quarter note and a fixed tempo of 120 BPM,
  which means 1 tick = 1.04 ms. Real-time event timestamps are converted
  to tick deltas at save time.
"""

from __future__ import annotations

import datetime
import logging
from pathlib import Path

import mido

logger = logging.getLogger(__name__)

TICKS_PER_BEAT = 480
TEMPO_BPM = 120
# At 120 BPM, one beat = 0.5 s, so 480 ticks per 0.5 s -> 960 ticks/sec.
_TICKS_PER_SECOND = TICKS_PER_BEAT * TEMPO_BPM / 60.0
_CHANNEL = 0


class MidiRecorder:
    """Records MIDI events to memory and writes a .mid file when stopped."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir
        self._events: list[tuple[float, mido.Message]] = []
        self._recording = False
        self._start_time: float | None = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def event_count(self) -> int:
        return len(self._events)

    def start(self, now: float, current_program: int) -> None:
        """Begin a fresh recording. The current instrument is captured so
        that playback starts on the right program.
        """
        if self._recording:
            logger.warning("MidiRecorder.start() called while already recording")
            return
        self._events = []
        self._recording = True
        self._start_time = now
        # Capture the starting instrument as the first event.
        self._events.append((
            0.0,
            mido.Message("program_change", channel=_CHANNEL, program=current_program),
        ))
        logger.info("Recording started")

    def record_note_on(self, now: float, midi_note: int, velocity: int) -> None:
        if not self._recording or self._start_time is None:
            return
        t = now - self._start_time
        self._events.append((
            t,
            mido.Message("note_on", channel=_CHANNEL, note=midi_note, velocity=velocity),
        ))

    def record_note_off(self, now: float, midi_note: int) -> None:
        if not self._recording or self._start_time is None:
            return
        t = now - self._start_time
        self._events.append((
            t,
            mido.Message("note_off", channel=_CHANNEL, note=midi_note, velocity=0),
        ))

    def record_program_change(self, now: float, program: int) -> None:
        if not self._recording or self._start_time is None:
            return
        t = now - self._start_time
        self._events.append((
            t,
            mido.Message("program_change", channel=_CHANNEL, program=program),
        ))

    def stop(self) -> Path | None:
        """Stop recording and write the MIDI file.

        Returns the saved file path, or None if nothing meaningful was
        captured (only the initial program-change event, no notes).
        """
        if not self._recording:
            logger.warning("MidiRecorder.stop() called when not recording")
            return None
        self._recording = False
        self._start_time = None

        if len(self._events) <= 1:
            logger.info("Recording stopped with no notes captured; not saving")
            self._events = []
            return None

        self._output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out_path = self._output_dir / f"composair_{timestamp}.mid"

        midi_file = mido.MidiFile(ticks_per_beat=TICKS_PER_BEAT)
        track = mido.MidiTrack()
        midi_file.tracks.append(track)

        # Tempo meta event so DAWs know the BPM.
        track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(TEMPO_BPM), time=0))

        # Convert wall-clock timestamps into tick deltas relative to previous event.
        previous_ticks = 0
        for event_time, msg in self._events:
            absolute_ticks = int(round(event_time * _TICKS_PER_SECOND))
            delta = max(0, absolute_ticks - previous_ticks)
            msg = msg.copy(time=delta)
            track.append(msg)
            previous_ticks = absolute_ticks

        track.append(mido.MetaMessage("end_of_track", time=0))
        midi_file.save(out_path)

        notes_recorded = sum(1 for _, m in self._events if m.type == "note_on")
        logger.info("Recording saved: %s (%d notes)", out_path, notes_recorded)
        self._events = []
        return out_path

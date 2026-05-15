"""Unit tests for MidiRecorder.

Writes a temp .mid file, parses it back with mido, and verifies the
recorded events match what we recorded.

Run from the project root:
    .venv\\Scripts\\python.exe tests\\test_recorder.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mido

from composair.recorder import MidiRecorder, TEMPO_BPM, TICKS_PER_BEAT


def _tmpdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="composair_test_"))


def test_stop_without_start_returns_none() -> None:
    rec = MidiRecorder(output_dir=_tmpdir())
    # start was never called; stop should be a no-op.
    assert rec.stop() is None


def test_recording_with_no_notes_does_not_save() -> None:
    rec = MidiRecorder(output_dir=_tmpdir())
    rec.start(now=0.0, current_program=0)
    out = rec.stop()
    assert out is None, "empty recording should not produce a file"


def test_records_note_on_and_off_with_correct_timing() -> None:
    out_dir = _tmpdir()
    rec = MidiRecorder(output_dir=out_dir)
    rec.start(now=10.0, current_program=0)
    # Note at t=0 (relative), off at t=1.0 s.
    rec.record_note_on(now=10.0, midi_note=60, velocity=100)
    rec.record_note_off(now=11.0, midi_note=60)
    path = rec.stop()
    assert path is not None and path.exists()

    mid = mido.MidiFile(path)
    track = mid.tracks[0]
    note_messages = [m for m in track if m.type in ("note_on", "note_off")]
    assert len(note_messages) == 2

    on, off = note_messages
    assert on.type == "note_on" and on.note == 60 and on.velocity == 100
    assert off.type == "note_off" and off.note == 60

    # Tick math: 1 second at 120 BPM with 480 ticks/beat = 960 ticks.
    # The note_off's delta from the previous event should be ~960.
    assert abs(off.time - 960) <= 2, f"expected delta near 960, got {off.time}"


def test_program_change_is_recorded() -> None:
    out_dir = _tmpdir()
    rec = MidiRecorder(output_dir=out_dir)
    rec.start(now=0.0, current_program=0)  # initial: piano
    rec.record_note_on(now=0.1, midi_note=60, velocity=100)
    rec.record_program_change(now=0.5, program=73)  # switch to flute
    rec.record_note_on(now=0.6, midi_note=64, velocity=100)
    rec.record_note_off(now=1.0, midi_note=60)
    rec.record_note_off(now=1.1, midi_note=64)
    path = rec.stop()
    assert path is not None

    mid = mido.MidiFile(path)
    track = mid.tracks[0]
    program_changes = [m for m in track if m.type == "program_change"]
    # Initial program=0 + switch to 73 = 2 program_change events.
    assert len(program_changes) == 2
    assert program_changes[0].program == 0
    assert program_changes[1].program == 73


def test_file_has_correct_tempo_and_ticks() -> None:
    out_dir = _tmpdir()
    rec = MidiRecorder(output_dir=out_dir)
    rec.start(now=0.0, current_program=0)
    rec.record_note_on(now=0.0, midi_note=60, velocity=100)
    rec.record_note_off(now=0.5, midi_note=60)
    path = rec.stop()
    assert path is not None

    mid = mido.MidiFile(path)
    assert mid.ticks_per_beat == TICKS_PER_BEAT

    tempo_meta = [m for m in mid.tracks[0] if m.type == "set_tempo"]
    assert len(tempo_meta) == 1
    expected_tempo = mido.bpm2tempo(TEMPO_BPM)
    assert tempo_meta[0].tempo == expected_tempo


def test_events_recorded_only_while_recording() -> None:
    rec = MidiRecorder(output_dir=_tmpdir())
    # Not started yet: these should be ignored.
    rec.record_note_on(now=0.0, midi_note=60, velocity=100)
    assert rec.event_count == 0

    rec.start(now=0.0, current_program=0)
    rec.record_note_on(now=0.0, midi_note=60, velocity=100)
    rec.record_note_off(now=0.5, midi_note=60)
    rec.stop()

    # After stop: ignored again.
    rec.record_note_on(now=1.0, midi_note=72, velocity=100)
    assert rec.event_count == 0


def main() -> int:
    tests = [
        test_stop_without_start_returns_none,
        test_recording_with_no_notes_does_not_save,
        test_records_note_on_and_off_with_correct_timing,
        test_program_change_is_recorded,
        test_file_has_correct_tempo_and_ticks,
        test_events_recorded_only_while_recording,
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

# ComposAir architecture and design notes

Internal design document for ComposAir. Captures the project overview, design decisions, build plan, and code conventions.

## Project overview

ComposAir is a real-time, finger-tracked MIDI instrument. The user plays it by pinching their thumb to a fingertip in front of a webcam; the program detects the pinch, picks a note from the current scale, and plays it through a built-in software synthesizer. An optional second hand provides continuous expression (volume, filter, vibrato).

ComposAir has two goals:
1. **Music-from-scratch idea capture** - output is MIDI, intended to be brought into a DAW (FL Studio / Reaper / Ableton / etc.) for arrangement, layering, and production. ComposAir is the input device + scratchpad, not a DAW replacement.
2. **Portfolio piece** - code quality, README polish, and demo-ability matter beyond just "it works on my machine." Treat this as something an interviewer will skim.

## Hardware / environment

- **OS:** Windows 11
- **Camera:** Emeet 4K AF USB webcam (capture at 1280x720; 4K offers no tracking benefit and hurts FPS)
- **Audio:** default Windows audio output
- **Editor:** VSCode

## Tech stack

| Layer | Library | Notes |
|---|---|---|
| Hand tracking | `mediapipe` (Tasks API: `mediapipe.tasks.vision.HandLandmarker`) | Use the new Tasks API, not the deprecated `solutions.hands` |
| Camera + UI overlay | `opencv-python` | |
| Synth | `pyFluidSynth` + GeneralUser GS SoundFont | Plays straight to speakers via `dsound` driver on Windows |
| Math | `numpy` | distances, velocity calculations |
| Config | `PyYAML` | All tunable values live in `config.yaml` |

**Python version:** 3.10-3.12. **Do not** use 3.13 - MediaPipe lacks Windows wheels for it.

## File structure

```
ComposAir/
├── composair/
│   ├── __init__.py
│   ├── main.py          # entry point, main loop
│   ├── tracker.py       # MediaPipe wrapper, landmark extraction
│   ├── gestures.py      # pinch detection, gesture-speed velocity
│   ├── synth.py         # FluidSynth wrapper, note on/off, CC, program change
│   ├── scales.py        # scale theory, key/scale data structures, transposition
│   ├── mapping.py       # finger + octave band → MIDI note number
│   ├── modulation.py    # second-hand → MIDI CC
│   ├── recorder.py      # MIDI file recording (Phase 5)
│   └── ui.py            # OpenCV overlay (landmarks, active fingers, key/scale display)
├── tests/
│   ├── test_camera.py   # smoke test: webcam works
│   ├── test_synth.py    # smoke test: FluidSynth plays a note
│   └── ...
├── soundfonts/          # .sf2 files (gitignored - too big)
├── documents/           # ComposAir architecture and design notes, README.md, timelines, planning docs
├── config.example.yaml  # checked in, copied to config.yaml on first run
├── config.yaml          # gitignored, user's actual config
└── requirements.txt
```

## Design decisions (and why)

**Pinch trigger.** Thumb-to-fingertip distance threshold. Intentional, reliable, gives clean note-on/note-off events. Tap-based triggers misfire; zones break flow.

**4 pinches per hand × hand height = octave bands.** 4 fingers (thumb-to-index/middle/ring/pinky) × 3-4 octave bands gives 12-16 notes from one hand. Bands are absolute Y ranges with hysteresis to prevent flicker at borders.

**Fingers default to scale degrees 1, 3, 5, 7.** Chord tones - anything played sounds musical. User-configurable to stepwise (1-2-3-4) or custom mapping via `config.yaml`.

**Always scale-locked.** The point is to make music, not hit wrong notes. Every output note snaps to the active key+scale.

**Velocity from gesture speed.** The rate of thumb-fingertip distance closure just before the pinch threshold maps to MIDI velocity (1-127). This is what makes it feel like an instrument vs. a switch.

**Second hand: modulation only, never plays notes.** Playing hand always plays; modulation hand always modulates. No mode-switching ambiguity. Default mapping: second-hand height → CC74 (filter cutoff).

**Built-in synth.** FluidSynth + a good SoundFont sounds dramatically better than Windows GS Wavetable. No DAW required.

## Phased build plan

We're building this in **phases**. Each phase produces a working, playable thing. **Do not skip ahead** - finish a phase, confirm it works, then move on.

1. **Walking skeleton** - webcam → MediaPipe → detect one pinch (thumb+index only) → play a fixed MIDI note. Goal: one sound from one pinch.
2. **Multi-finger play** - all 4 pinches on one hand → 4 fixed notes, proper note-on/note-off lifecycle, visual overlay showing active finger.
3. **Scale system + octave shift** - `scales.py` with major, minor, pentatonic (major + minor), dorian, harmonic minor. Hand Y → octave band. Fingers → scale degrees per `config.yaml`.
4. **Velocity from gesture speed** - replace fixed velocity 100 with gesture-speed-derived velocity. Needs a short window of recent positions per fingertip.
5. **MIDI file recording** - `recorder.py` captures note-on/note-off events with timestamps, writes a valid `.mid` file on stop. Toggle via `R` hotkey. **This is load-bearing for the user's DAW-paired workflow** - promoted ahead of second-hand modulation.
6. **Second-hand modulation** - detect both hands, classify left vs. right, map non-playing hand's Y to a CC. Recorded into the MIDI file as a CC track.
7. **Key/scale/instrument switching** - keyboard hotkeys to change key (1-7), scale (single letters), and instrument ([/]). On-screen indicator.
8. **Polish** - latency tuning, demo video/GIF for README, screenshots, architecture diagram, README portfolio pass.

**Current phase: 1 (walking skeleton) - environment set up, no Phase 1 code yet.**

## Code conventions

- **Type hints on all functions.** Use `from __future__ import annotations` at the top of every module.
- **Docstrings** (Google style) on every public function and class.
- **One module per responsibility.** Keep `main.py` lean - it should read like an outline of the loop.
- **Logging, not print.** Configure `logging` once in `main.py`. Use module-level loggers (`logger = logging.getLogger(__name__)`).
- **Constants in `UPPER_CASE`** at module top.
- **No global mutable state.** Pass dependencies in via constructors.
- **No magic numbers.** Tunable values (thresholds, framerates, CC numbers) live in `config.yaml`.
- **Dataclasses** for value types (e.g., `HandState`, `PinchEvent`, `Note`).

## Common commands

```powershell
# Activate venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python -m composair.main

# Smoke tests
python tests/test_camera.py
python tests/test_synth.py
```

## Non-goals (don't build these unless asked)

- MIDI input from external controllers
- Multi-user / networked play
- Audio recording (MIDI file recording is fine, audio is out of scope)
- A full GUI beyond the OpenCV overlay
- Custom-trained gesture models
- Mobile or web versions

## Implementation notes

- **Confirm the current phase** with the user before generating large amounts of code. Don't write Phase 4 code when Phase 2 isn't done.
- **Prefer small, runnable increments** over large drops. Each step should be testable in isolation.
- **When you add a module, add a tests file** in `tests/` alongside it.
- **If a value feels like it should be configurable, put it in `config.yaml`** rather than hardcoding.
- The user is learning Python and data analytics; favor clear, idiomatic code over clever one-liners, and explain non-obvious choices in comments or commit messages.

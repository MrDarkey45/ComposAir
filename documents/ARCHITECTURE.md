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
│   ├── main.py             # entry point, main loop, hotkey dispatch
│   ├── camera.py           # cv2.VideoCapture wrapper with retry dialog
│   ├── tracker.py          # MediaPipe HandLandmarker wrapper, TrackedHand
│   ├── gestures.py         # Point2D/Point3D, PinchDetector, VelocityEstimator
│   ├── synth.py            # FluidSynth wrapper: note_on/off, CC, program_change
│   ├── scales.py           # key/scale theory, ScaleSpec, degree-to-MIDI
│   ├── mapping.py          # OctaveBandSelector (hand Y to octave with hysteresis)
│   ├── modulation.py       # ModulationMapper (Y to CC value, smoothing, deadzone)
│   ├── recorder.py         # MidiRecorder (mido-backed MIDI file writer)
│   ├── smoothing.py        # one-euro filter for landmark jitter (opt-in)
│   ├── hotkeys.py          # ActionType, HotkeyAction, resolve(keycode)
│   ├── settings_panel.py   # Tkinter live-tuning window
│   ├── gm_instruments.py   # General MIDI program 0-127 name table
│   ├── config.py           # Config dataclass + YAML loader with validation
│   └── ui.py               # OpenCV overlay drawing helpers
├── tests/                  # 69 unit tests across 6 modules
├── models/                 # MediaPipe hand_landmarker.task (gitignored, ~8MB)
├── soundfonts/             # GeneralUser-GS.sf2 (gitignored, ~30MB)
├── recordings/             # MIDI output (gitignored)
├── documents/              # ComposAir architecture and design notes, README.md, STARTUP.txt (local)
├── config.example.yaml     # checked in template with documentation
├── config.yaml             # gitignored, user's overrides
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

1. **Walking skeleton** - DONE. Webcam to MediaPipe to thumb+index pinch to middle C.
2. **Multi-finger play** - DONE. All 4 thumb-to-finger pinches on one hand fire 4 fixed notes with proper polyphony.
3. **Scale system + octave shift** - DONE. `scales.py` with major, natural/harmonic minor, dorian, major/minor pentatonic. Hand Y maps to octave bands with hysteresis; fingers map to scale degrees per config.
4. **Velocity from gesture speed** - DONE. Pinch closure rate drives MIDI velocity via per-finger ring buffer in VelocityEstimator.
5. **MIDI file recording + instrument switching** - DONE. `recorder.py` captures note + program + CC events with timestamps. R toggles record, [ ] cycle instruments. Output is DAW-ready type-1 SMF.
6. **Second-hand modulation** - DONE. Two-hand classification via MediaPipe handedness. Non-playing hand drives CC 7 (volume) by default; CC events captured into the .mid.
7. **Key/scale/instrument switching + polish** - DONE in three sub-phases:
   - **7A**: live key/scale hotkeys (1-7 for keys, M/n/h/d/P/p for scales). Pinch thresholds re-tuned from 0.12 to 0.18 based on dexterity feedback.
   - **7B**: optional one-euro landmark smoothing (`smoothing.py`). Disabled by default - the cure was worse than the disease on a clean webcam.
   - **7C**: opt-in 3D world-landmark pinch detection, Tkinter settings panel (S hotkey), per-finger 2D thresholds.
8. **Portfolio prep + packaging** - in progress:
   - **8A**: README portfolio pass, camera readiness dialog, internal docs sync, architecture diagram.
   - **8B**: demo video / GIF / screenshots (user-captured on their own time).
   - **8C**: PyInstaller .exe spike for end-user distribution.

**Polish items deferred (not blocking, worth a future pass):**
- 3D landmarks have their own depth-ambiguity problem at extreme hand angles, so 2D is the default. Revisit when MediaPipe ships a better monocular depth model.
- Smoothing is opt-in. Users with noisier cameras may benefit.

**Current state:** Every functional phase shipped (1 through 7C). 69 unit tests passing. Phase 8 in progress.

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

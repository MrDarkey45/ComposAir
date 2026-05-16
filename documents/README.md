# ComposAir

> A finger-tracked MIDI instrument. Pinch your fingers in the air to play notes, raise your hand to shift octaves, move the other hand to shape the sound. Record your performance as a standard MIDI file and drag it into any DAW.

ComposAir watches your hand through a webcam, detects when you pinch your thumb to a fingertip, and plays a note from your chosen key and scale through a built-in software synthesizer. Hand height shifts octaves. Pinch speed sets velocity. The non-playing hand modulates expression. Capture your ideas as `.mid` files and bring them into FL Studio, Reaper, Ableton, or GarageBand for arrangement.

## Why ComposAir

If you want to make music but can't (or don't want to) play a physical instrument, the usual entry points - piano roll, step sequencers, MIDI keyboards - all assume some musical fluency. ComposAir flips the model: **gestures in, scale-locked MIDI out.** Anything you play sounds musical because the scale is enforced before a note ever fires. Capture the result as a `.mid` file, pull it into your DAW, layer drums and harmony around it, and you have the spine of a track.

## Features

- **Real-time hand tracking** via MediaPipe; runs on any modern CPU, no GPU required
- **Two-hand support**: one hand plays notes, the other modulates expression (default: volume sweeps)
- **Scale-locked playing** - pick from 12 keys × 6 scales (major, natural/harmonic minor, dorian, major/minor pentatonic) and nothing you play sounds "wrong"
- **Per-finger calibration** - tune each finger's pinch sensitivity independently
- **Expressive velocity** from pinch speed - soft pinches play softly, fast pinches play loudly
- **Hand-height octave shift** with hysteresis to prevent flicker between octaves
- **Continuous MIDI Control Change** from the second hand's position (volume, filter, mod wheel, pan, or any of the 128 CCs)
- **MIDI file recording** with timestamped note + program-change + CC events; output drops straight into any DAW
- **128 General MIDI instruments** via the bundled SoundFont, cycled live with `[` / `]`
- **In-app settings panel** (Tkinter window) for live retuning without restart
- **Live key / scale / instrument hotkeys** so you can change the music while playing
- **Opt-in 3D world-landmark pinch detection** and **opt-in one-euro landmark smoothing** for users with noisier cameras
- Built-in software synth via FluidSynth + GeneralUser GS SoundFont; plays straight to your speakers, no DAW required

## How to play

1. Hold your dominant hand in front of the camera, palm facing the screen.
2. **Pinch** your thumb to a fingertip to play a note:
   - Thumb + Index -> scale degree 1 (root)
   - Thumb + Middle -> scale degree 3
   - Thumb + Ring -> scale degree 5
   - Thumb + Pinky -> scale degree 7
3. **Hand height** sets the octave - higher position, higher octave.
4. **Pinch speed** sets velocity - slow = soft, fast = loud.
5. Raise your **second hand** into frame to modulate volume continuously (or any other MIDI CC you set in config).
6. Use keyboard hotkeys to change key, scale, and instrument while playing.
7. Press **R** to start recording a MIDI file; press **R** again to stop and save.

### Hotkeys

| Key | Action |
|---|---|
| `Q` | Quit |
| `R` | Start / stop MIDI file recording (saved to `recordings/`) |
| `S` | Open settings panel for live tuning |
| `[` / `]` | Previous / next instrument |
| `1` - `7` | Change key (C, D, E, F, G, A, B) |
| `M` | Major scale |
| `n` | Natural minor |
| `h` | Harmonic minor |
| `d` | Dorian |
| `P` | Major pentatonic |
| `p` | Minor pentatonic |

The camera window must have focus for hotkeys to work; click on it before pressing.

## How it works

```
Webcam frame  ->  MediaPipe HandLandmarker  ->  TrackedHand
                                                    |
                       +----------------------------+
                       |                            |
              playing hand                  modulation hand
                       |                            |
        Pinch detector per finger          ModulationMapper
        (thumb-finger distance,             (hand Y -> CC value
         normalized by hand size,            with smoothing
         with hysteresis)                    and deadzone)
                       |                            |
       VelocityEstimator                            |
       (slope of distance                           |
        over recent samples)                        |
                       |                            |
       ScaleSpec resolver                           |
       (key + scale + degree                        |
        + octave band -> MIDI                       |
        note number)                                |
                       |                            |
                       +-------------+--------------+
                                     |
                              FluidSynth + MidiRecorder
                                     |
                       Speakers                .mid file
```

Each module owns one responsibility and is unit-tested in isolation. The main loop reads one camera frame, asks the tracker for the latest hand classification, routes the playing hand through pinch detection / scale resolution / velocity estimation, routes the modulation hand through the CC mapper, and dispatches the resulting MIDI events to both the synth (immediate playback) and the recorder (if recording is active).

## Requirements

- **OS:** Windows 10/11 (primary). The code is mostly cross-platform but FluidSynth audio driver setup differs on macOS / Linux.
- **Python:** 3.10 - 3.12 (MediaPipe does not yet ship Windows wheels for 3.13).
- **Webcam:** any USB or built-in webcam at 720p or higher, 30 FPS recommended.
- **Audio:** any output device. Wired headphones recommended; Bluetooth headphones add 100-200 ms of latency that makes the instrument feel sluggish.

## Installation

### 1. Install FluidSynth (the C library)

pyFluidSynth is a Python wrapper - the actual synth engine is a separate install.

**Windows:**
1. Download `fluidsynth-vX.X.X-win10-x64-glib.zip` from [FluidSynth releases](https://github.com/FluidSynth/fluidsynth/releases).
2. Extract somewhere stable (e.g. `C:\fluidsynth\` or `D:\FluidSynth\`).
3. Add the extracted `bin` directory to your User `PATH`.

**macOS:** `brew install fluidsynth`

**Linux (Debian/Ubuntu):** `sudo apt install fluidsynth`

Verify in a fresh terminal: `fluidsynth --version`.

### 2. Download a SoundFont

[GeneralUser GS](https://www.schristiancollins.com/generaluser.php) is the recommended default. Save the `.sf2` file to `soundfonts/` in the project root. Any GM-compatible SoundFont works; update `soundfont:` in `config.yaml` if you use a different file.

### 3. Download the MediaPipe HandLandmarker model

```
mkdir models
# Then download:
# https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task
# Save to models/hand_landmarker.task
```

### 4. Set up the Python environment

```bash
git clone <this-repo-url>
cd ComposAir
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Run

```bash
python -m composair.main
```

A camera window opens. Pinch to play. Press `Q` to quit. Settings are read from `config.yaml` if present, else `config.example.yaml`.

## Configuration

All tunable behavior lives in `config.example.yaml`. Copy to `config.yaml` and edit, or press `S` while the app is running to open the in-app settings panel which writes back to `config.yaml` automatically.

The most commonly tuned values:

| Setting | Default | Notes |
|---|---|---|
| `pinch_thresholds.<finger>.on` | 0.18 | trigger sensitivity per finger; lower = harder to trigger |
| `pinch_thresholds.<finger>.off` | 0.23 | release threshold; must be > on |
| `instrument` | 0 | General MIDI program number; 0 = Acoustic Grand Piano |
| `key` | C | musical key |
| `scale` | major | scale name |
| `modulation.cc_number` | 7 | MIDI CC the second hand drives (7 = volume) |
| `octave_bands.count` | 3 | how many vertical bands divide the screen |

See `config.example.yaml` for the full documented schema.

## Tech stack

- [MediaPipe](https://developers.google.com/mediapipe) - hand tracking (Tasks API, HandLandmarker)
- [OpenCV](https://opencv.org/) - webcam capture and overlay rendering
- [pyFluidSynth](https://github.com/nwhitehead/pyfluidsynth) + [FluidSynth](https://www.fluidsynth.org/) - software synthesizer
- [mido](https://mido.readthedocs.io/) - MIDI file writing
- [NumPy](https://numpy.org/) - distance math
- [PyYAML](https://pyyaml.org/) - configuration
- Tkinter (Python standard library) - settings panel

## Troubleshooting

**Camera dialog says "Camera not available"**
Another app is probably holding the camera (Teams, Zoom, OBS, browser tab, Windows Camera app). Close it and click Retry. If you have multiple cameras, try changing `camera_index` in `config.yaml` to 1 or 2.

**`fluidsynth --version` not found after install**
PATH didn't update. Open a fresh terminal. If still missing, double-check that the directory you added to PATH actually contains `fluidsynth.exe`.

**`OSError: libfluidsynth` / DLL load error on Python import**
pyFluidSynth's loader looks at `C:\tools\fluidsynth\bin` on Windows. If you installed somewhere else, create a directory junction so it points to your real install: `mklink /J C:\tools\fluidsynth D:\YourFluidSynthPath`.

**Notes are laggy / FPS is low**
Lower `camera_width` and `camera_height` in `config.yaml`; 640x480 is fine for tracking. Use wired audio. Close other CPU-heavy apps.

**No sound but no errors**
Check that the SoundFont path in `config.yaml` matches the actual filename. Check which audio device Windows is sending output to.

**Pinches feel unreliable**
Open the settings panel with `S` and adjust per-finger thresholds. The `closest: <finger> d = ...` readout at the bottom of the camera window shows the live normalized distance value; set each finger's trigger slightly above its typical touching value.

## License

MIT
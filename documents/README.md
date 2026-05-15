# ComposAir

> Compose music in the air. A finger-tracked MIDI instrument that turns your webcam into an expressive controller for music creation.

ComposAir watches your hand through a webcam, detects when you pinch your thumb to a fingertip, and plays a note from your chosen key and scale through a built-in software synthesizer. Hand height shifts octaves. Pinch speed sets velocity. An optional second hand modulates expression. Capture your ideas as MIDI files and bring them into your DAW for arrangement - no physical instrument required.

## Why ComposAir

If you want to make music but can't (or don't want to) play a physical instrument, the usual entry points - piano roll, step sequencers, MIDI keyboards - all assume some musical fluency. ComposAir flips the model: **gestures in, scale-locked MIDI out.** Anything you play sounds musical, because the scale is enforced before a note ever fires. Capture the result as a `.mid` file, pull it into FL Studio / Reaper / Ableton / GarageBand, layer drums and harmony around it, and you have the spine of a track.

## Features

- **Real-time hand tracking** via MediaPipe - works on any modern CPU, no GPU required
- **Built-in software synth** via FluidSynth + a General MIDI SoundFont - plays straight to your speakers
- **Scale-locked playing** - pick a key and scale, and nothing you play will sound "wrong"
- **Expressive velocity** from pinch speed - soft pinches play softly, fast pinches play loudly
- **Hand-height octave shift** - same fingers, different octaves
- **Optional second hand for modulation** - continuous control over filter, volume, or vibrato
- **MIDI file recording** - capture your performance as a `.mid` for use in any DAW
- **On-the-fly key, scale, and instrument changes** via keyboard hotkeys
- **General MIDI instruments** - piano, electric piano, strings, synth pad, anything in the SoundFont

## How to play

1. Hold your dominant hand in front of the camera, palm facing the screen.
2. **Pinch** your thumb to a fingertip to play a note:
   - Thumb + Index → scale degree 1 (root)
   - Thumb + Middle → scale degree 3
   - Thumb + Ring → scale degree 5
   - Thumb + Pinky → scale degree 7
3. **Hand height** sets the octave - higher position, higher octave.
4. **Pinch speed** sets velocity - slow = soft, fast = loud.
5. (Optional) Raise your **second hand** into frame to modulate expression continuously.
6. Use the keyboard to change **key**, **scale**, and **instrument** while playing.
7. Press **R** to start recording a MIDI file; press **R** again to stop and save.

## Requirements

- **OS:** Windows 10/11 (primary), macOS, or Linux
- **Python:** 3.10-3.12 (MediaPipe does not yet support 3.13 on Windows)
- **Webcam:** any USB or built-in webcam
- **Audio:** standard audio output (wired headphones recommended for lowest latency)

Recommended: a USB keyboard within reach so you can change keys/scales while playing.

## Installation

### 1. Install FluidSynth (the C library)

pyFluidSynth is a Python wrapper - the actual synth engine needs to be installed separately.

**Windows:**
1. Download the latest `fluidsynth-vX.X.X-win10-x64-glib.zip` from [FluidSynth releases](https://github.com/FluidSynth/fluidsynth/releases).
2. Extract to a stable location, e.g. `C:\fluidsynth\` (or anywhere - just note the path).
3. Add the extracted `bin` directory to your `PATH` (System Properties → Environment Variables → Path → Edit → New).

**macOS:**
```bash
brew install fluidsynth
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install fluidsynth
```

Verify the install (open a fresh terminal):
```bash
fluidsynth --version
```

### 2. Download a SoundFont

[GeneralUser GS](https://www.schristiancollins.com/generaluser.php) is the recommended default - free, well-regarded, covers the full General MIDI instrument set. Save the `.sf2` file to a `soundfonts/` folder in the project root.

Any GM-compatible SoundFont will work; update the path in `config.yaml` accordingly.

### 3. Set up the Python environment

```bash
git clone <this-repo-url>
cd ComposAir

# Create and activate a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 4. Configure

Copy the example config and edit if needed:
```bash
# Windows:
copy config.example.yaml config.yaml
# macOS / Linux:
cp config.example.yaml config.yaml
```

Key settings:
```yaml
soundfont: soundfonts/GeneralUser-GS.sf2
instrument: 0          # 0 = Acoustic Grand Piano (GM program number)
camera_index: 0        # change if you have multiple cameras
camera_width: 1280
camera_height: 720
key: C
scale: major
pinch_threshold: 0.05  # normalized distance; lower = harder to trigger
```

## Usage

```bash
python -m composair.main
```

A camera window opens with a tracking overlay. Pinch to play. Press `Q` to quit.

### Hotkeys

| Key | Action |
|---|---|
| `1` - `7` | Change key (C, D, E, F, G, A, B) |
| `M` | Major scale |
| `n` | Natural minor |
| `P` | Major pentatonic |
| `p` | Minor pentatonic |
| `d` | Dorian |
| `[` / `]` | Previous / next instrument |
| `R` | Start / stop MIDI file recording |
| `Q` | Quit |

*Hotkeys are added progressively across phases; earlier builds use config-file values only.*

## Roadmap

- [ ] **Phase 1:** Walking skeleton - pinch → note
- [ ] **Phase 2:** Multi-finger play (4 notes per hand)
- [ ] **Phase 3:** Scale system + octave shift via hand height
- [ ] **Phase 4:** Velocity from gesture speed
- [ ] **Phase 5:** MIDI file recording (export to DAW-ready `.mid`)
- [ ] **Phase 6:** Second-hand modulation
- [ ] **Phase 7:** Key / scale / instrument switching
- [ ] **Phase 8:** Polish - latency tuning, screenshots/demo video, documentation

## Tech stack

- [MediaPipe](https://developers.google.com/mediapipe) - hand tracking
- [OpenCV](https://opencv.org/) - webcam capture, visualization
- [pyFluidSynth](https://github.com/nwhitehead/pyfluidsynth) + [FluidSynth](https://www.fluidsynth.org/) - software synthesizer
- [NumPy](https://numpy.org/) - math
- [PyYAML](https://pyyaml.org/) - config

## Troubleshooting

**`fluidsynth --version` not found after install**
PATH didn't update. Open a *new* terminal window. If still missing, double-check the directory you added contains `fluidsynth.exe`.

**`OSError: libfluidsynth.so` / DLL load error**
The Python wrapper can't find the FluidSynth library. On Windows, confirm your FluidSynth `bin` directory is on PATH. On macOS, `brew --prefix fluidsynth` should return a path; if not, reinstall via Homebrew.

**Camera doesn't open**
Try a different `camera_index` in `config.yaml` (`0`, `1`, `2`...). On Windows, close any other app that might be holding the camera (Teams, OBS, browser tabs).

**Notes are laggy / FPS is low**
Lower `camera_width` / `camera_height` in `config.yaml`. 1280x720 is the recommended max; 640x480 is fine for tracking. Also try wired headphones - Bluetooth audio adds 100-200 ms of latency.

**No sound but no errors**
Confirm the SoundFont path in `config.yaml` exists and matches the actual filename. Check the audio output device selected in Windows.

## License

MIT

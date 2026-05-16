# ComposAir

A webcam-based MIDI instrument. You pinch your fingers in the air, the program watches your hands and plays notes. Record what you play and drop the file into a DAW.

I built this because I wanted to make music for video games but I don't play any instruments. The usual entry points (piano roll, MIDI keyboards, step sequencers) all assume some musical background I don't have. ComposAir lets you noodle around with your hands until something sounds good, captures it as a `.mid`, and you take it into FL Studio / Reaper / Ableton / GarageBand to build a song around it.

## What it does

- Tracks both your hands through the webcam in real time
- Pinch your thumb to any of your four fingers to play a note (so four notes per hand)
- Raise/lower your hand to change octaves
- Pinch slowly for a quiet note, snap your fingers for a loud one
- The non-playing hand controls volume (or any other MIDI knob you pick) by its height
- Pick a key and scale and nothing you play will sound "wrong"
- Press `R` to record what you're playing as a `.mid` file
- Press `S` to open a settings window so you can tune the pinch sensitivity per finger without restarting
- 128 General MIDI instruments built in (piano, strings, synths, guitars, etc.), cycle them live with `[` and `]`

## Honest limitations

- The pinch detection is 2D by default and gets a bit weird when fingers occlude each other or when your hand is at a sharp angle to the camera. There is a 3D mode in the config but it has its own depth-ambiguity problems so it ships off.
- The instrument is good for capturing melodic ideas. It is not a substitute for a real keyboard if you have one.
- Bluetooth headphones add enough audio lag that pinches feel delayed. Wired audio is much better.

## How to play

1. Hold your dominant hand in front of the camera, palm toward the screen.
2. Pinch your thumb to a fingertip to play a note:
   - Thumb + Index = scale degree 1 (root)
   - Thumb + Middle = scale degree 3
   - Thumb + Ring = scale degree 5
   - Thumb + Pinky = scale degree 7
3. Hand height sets the octave. Higher hand = higher pitch.
4. Pinch speed sets velocity. Slow = soft, fast = loud.
5. Raise your other hand into frame to swell the volume (or any other CC you set in config).
6. Use the keyboard to change key, scale, and instrument while playing.
7. Press `R` to start recording, `R` again to stop and save.

### Hotkeys

The camera window has to have focus for these to work; click on it before pressing.

| Key | What it does |
|---|---|
| `Q` | Quit |
| `R` | Start / stop MIDI file recording |
| `S` | Open the settings panel |
| `[` / `]` | Previous / next instrument |
| `1` - `7` | Change key (1=C, 2=D, 3=E, 4=F, 5=G, 6=A, 7=B) |
| `M` | Major scale |
| `n` | Natural minor |
| `h` | Harmonic minor |
| `d` | Dorian |
| `P` | Major pentatonic |
| `p` | Minor pentatonic |

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

OpenCV pulls a frame from the webcam. MediaPipe finds hands in the frame and gives back 21 landmark points per hand. We classify which hand plays and which modulates (via MediaPipe's left/right detection or a config override). For the playing hand we measure thumb-to-fingertip distances; when one drops below a threshold we fire a MIDI note-on, with the velocity derived from how fast the distance was shrinking. The note number comes from a key+scale+degree+octave lookup. FluidSynth turns the MIDI event into audio. If recording is on, mido captures the event with a timestamp and writes a standard MIDI file when you stop.

Each module owns one thing and has unit tests. There are 69 of them across the math layers (gesture distances, pinch state machine, velocity estimator, scale theory, octave band hysteresis, MIDI file format, CC mapping, one-euro filter, hotkey table).

## Tech stack

| Library | Role | Notes |
|---|---|---|
| MediaPipe | Hand tracking | Google's pre-trained model, runs on CPU at 30 FPS |
| OpenCV | Webcam capture + overlay rendering | Cross-platform, the standard for this |
| pyFluidSynth + FluidSynth | Software synthesizer | Plays SoundFonts; FluidSynth is a separate C-library install |
| GeneralUser GS SoundFont | 128 GM instruments in one ~30 MB file | Default sound source |
| mido | MIDI file writing | Pure Python, no native deps |
| NumPy | Distance math | Just `hypot` / `sqrt` |
| PyYAML | Config | Plain-text config file |
| Tkinter | In-app settings window | Stdlib, no extra dependency |
| PyInstaller | Build the standalone .exe | Bundles everything into one folder |

## Requirements

- Windows 10 or 11 (the code is mostly cross-platform but I have only tested on Windows)
- Python 3.10-3.12 (MediaPipe does not ship Windows wheels for 3.13+ yet)
- Any webcam at 720p / 30 FPS or better
- Wired headphones or speakers (Bluetooth audio has too much latency)

## Installation

### 1. Install FluidSynth (the C library, separate from the Python wrapper)

**Windows:**
1. Download `fluidsynth-vX.X.X-win10-x64-glib.zip` from the [FluidSynth releases page](https://github.com/FluidSynth/fluidsynth/releases).
2. Extract somewhere stable like `C:\fluidsynth\` or `D:\FluidSynth\`.
3. Add the `bin` folder inside that to your User `PATH`.
4. Open a new terminal and run `fluidsynth --version` to confirm.

**macOS:** `brew install fluidsynth`

**Linux (Debian/Ubuntu):** `sudo apt install fluidsynth`

### 2. Download a SoundFont

Get [GeneralUser GS](https://www.schristiancollins.com/generaluser.php) and save the `.sf2` file to `soundfonts/` in the project root.

### 3. Download the MediaPipe hand tracking model

Make a `models/` folder in the project root and download `hand_landmarker.task` into it from:
`https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task`

### 4. Set up Python

```bash
git clone <this repo>
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

A camera window opens. Pinch to play. Press `Q` to quit. Settings load from `config.yaml` if it exists, otherwise from `config.example.yaml`.

## Configuration

Everything tunable lives in `config.example.yaml`. Copy it to `config.yaml` and edit, or press `S` while the app is running and use the settings window which writes back to `config.yaml` for you.

The things you will most likely want to tune:

| Setting | Default | What it does |
|---|---|---|
| `pinch_thresholds.<finger>.trigger` | 0.18 | Lower = harder to trigger a note for that finger |
| `pinch_thresholds.<finger>.release` | 0.23 | How relaxed the pinch can get before releasing the note |
| `instrument` | 0 | General MIDI program (0 = piano, 73 = flute, 81 = synth lead, etc.) |
| `key` | C | Musical key |
| `scale` | major | major, natural_minor, harmonic_minor, dorian, major_pentatonic, minor_pentatonic |
| `modulation.cc_number` | 7 | Which MIDI controller the second hand drives. 7 = volume. |
| `octave_bands.count` | 3 | How many vertical bands the screen is split into |

The full schema with comments is in `config.example.yaml`.

## Troubleshooting

**"Camera not available" dialog at startup**
Something else is holding the camera. Close Teams, Zoom, OBS, browser tabs, or the Windows Camera app and click Retry. If you have multiple cameras try changing `camera_index` in `config.yaml` to 1 or 2.

**`fluidsynth --version` says command not found**
PATH probably did not update. Open a fresh terminal. If it still does not work, double-check the directory you added to PATH actually contains `fluidsynth.exe`.

**DLL load error when starting Python**
pyFluidSynth's loader looks at `C:\tools\fluidsynth\bin` for its DLLs. If you installed FluidSynth somewhere else, make a directory junction:
```
mklink /J C:\tools\fluidsynth D:\YourFluidSynthPath
```

**Notes are laggy or FPS is low**
Lower `camera_width` and `camera_height` in `config.yaml`. 640x480 is fine for tracking. Use wired audio. Close other heavy apps.

**Pinches feel unreliable**
Open the settings panel with `S`. The bottom of the camera window shows `closest: <finger> d = ...` which is the live distance value. Set each finger's trigger just above its typical touching value. The middle and ring fingers usually need a slightly higher threshold than index and pinky.

**No sound but no errors**
Check the soundfont path in `config.yaml` matches the actual filename. Check which audio device Windows is sending output to.

## What I learned building this

A few things I would not have known going in:

- Real-time hand tracking is more about handling jitter and edge cases than about the tracking itself. The model gives you landmarks; the hard part is what you do when one finger briefly hides another or when the hand tilts at a weird angle.
- Latency budgets matter more than you think. End-to-end (webcam to hearing the note) needs to be under about 50 ms to feel like an instrument; above that it feels like a switch.
- Music theory is unforgiving but bounded. Scales are just lists of semitone offsets; chord tones are scale degrees 1/3/5/7; everything else is bookkeeping.
- YAML's `on` and `off` keys silently become booleans. Found this one when the .exe crashed on a saved config. Renamed to `trigger` and `release`.

## License

MIT

"""ComposAir entry point.

Phase 7A: webcam -> two-hand tracking -> playing hand drives pinch /
scale / octave / velocity, modulation hand drives a Control Change.
Hotkeys: 1-7 select the key (C, D, E, F, G, A, B); M/n/h/d/P/p select
the scale; [ ] cycle instruments; R toggles MIDI recording; Q quits.

Run from the project root:
    python -m composair.main
"""

from __future__ import annotations

import logging
import sys
import time

from pathlib import Path

import cv2

from .config import load_config
from .gestures import (
    ALL_FINGERS,
    Finger,
    MIDDLE_FINGER_MCP,
    PinchDetector,
    PinchEvent,
    VelocityEstimator,
    normalized_pinch_distance,
    normalized_pinch_distance_3d,
)
from .hotkeys import ActionType, resolve as resolve_hotkey
from .mapping import OctaveBandSelector, resolve_midi_note
from .modulation import ModulationMapper
from .recorder import MidiRecorder
from .scales import ScaleSpec
from .settings_panel import TunableSettings, open_settings_panel
from .synth import Synth
from .tracker import HandTracker, TrackedHand
from .ui import (
    draw_cc_bar,
    draw_fps,
    draw_hand,
    draw_help,
    draw_instrument_readout,
    draw_modulation_hand,
    draw_octave_bands,
    draw_pinch_indicators,
    draw_rec_indicator,
    draw_scale_readout,
    draw_velocity_readout,
)

WINDOW_TITLE = "ComposAir"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RECORDINGS_DIR = PROJECT_ROOT / "recordings"
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
CONFIG_EXAMPLE_PATH = PROJECT_ROOT / "config.example.yaml"

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    configure_logging()
    cfg = load_config()

    cap = cv2.VideoCapture(cfg.camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        logger.error("Could not open camera %d", cfg.camera_index)
        return 1
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.camera_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.camera_height)
    cap.set(cv2.CAP_PROP_FPS, cfg.camera_fps)
    logger.info("Camera opened: %dx%d @ %.1f FPS",
                int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                cap.get(cv2.CAP_PROP_FPS))

    # One detector + one velocity estimator per finger so they fire
    # independently. Live tunables are kept mutable so the settings panel
    # can adjust them without restarting the loop.
    tunables = TunableSettings(
        pinch_thresholds_2d={f: cfg.pinch_thresholds_2d[f] for f in ALL_FINGERS},
        use_3d_pinches=cfg.use_3d_pinches,
        pinch_threshold_3d=cfg.pinch_threshold_3d,
        pinch_release_3d=cfg.pinch_release_3d,
        fast_closure_rate=cfg.velocity.fast_closure_rate,
    )
    if tunables.use_3d_pinches:
        logger.info("Using 3D world-landmark pinch detection (on=%.3f, off=%.3f)",
                    tunables.pinch_threshold_3d, tunables.pinch_release_3d)
        detectors: dict[Finger, PinchDetector] = {
            finger: PinchDetector(
                on_threshold=tunables.pinch_threshold_3d,
                off_threshold=tunables.pinch_release_3d,
            )
            for finger in ALL_FINGERS
        }
    else:
        logger.info("Using 2D screen-landmark pinch detection (per-finger thresholds)")
        for finger in ALL_FINGERS:
            on, off = tunables.pinch_thresholds_2d[finger]
            logger.info("  %s: on=%.3f off=%.3f", finger.value, on, off)
        detectors = {
            finger: PinchDetector(
                on_threshold=tunables.pinch_thresholds_2d[finger][0],
                off_threshold=tunables.pinch_thresholds_2d[finger][1],
            )
            for finger in ALL_FINGERS
        }
    estimators: dict[Finger, VelocityEstimator] = {
        finger: VelocityEstimator(cfg.velocity) for finger in ALL_FINGERS
    }
    selector = OctaveBandSelector(cfg.octave_bands)
    # spec is mutable: hotkeys replace it with a new frozen instance on key/scale change.
    spec = ScaleSpec(key=cfg.key, scale_name=cfg.scale)
    recorder = MidiRecorder(output_dir=RECORDINGS_DIR)
    modulator = ModulationMapper(cfg.modulation)

    # MIDI note that each currently-held finger committed to at note-on,
    # so note-off sends the matching value even if the hand has moved bands.
    held_notes: dict[Finger, int] = {}
    # Most recent velocity resolved per finger, for the UI readout.
    last_velocity: dict[Finger, int] = {}
    # Timestamp of the last CC emission so we can throttle the rate.
    last_cc_send_time = 0.0

    with Synth(soundfont=cfg.soundfont, instrument=cfg.instrument,
               audio_driver=cfg.audio_driver, sample_rate=cfg.sample_rate) as synth, \
         HandTracker(num_hands=2, smoothing=cfg.smoothing) as tracker:

        frame_count = 0
        fps_window_start = time.perf_counter()
        fps = 0.0

        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    logger.warning("Camera read failed; skipping frame")
                    continue

                # Mirror horizontally so the user's right hand appears on the
                # right side of the screen. Feels natural like a mirror.
                frame = cv2.flip(frame, 1)

                tracker.submit_frame(frame)
                hands = tracker.latest_hands()

                # Per-frame snapshot of state used by the UI.
                distances: dict[Finger, float] = {}
                pinched: dict[Finger, bool] = {}
                current_band = selector.current_band
                now = time.perf_counter()

                playing_hand, modulation_hand = _classify_hands(
                    hands, cfg.playing_hand, cfg.dominant_hand
                )

                if playing_hand is not None:
                    landmarks = playing_hand.landmarks
                    world = playing_hand.world_landmarks
                    # Middle-finger MCP (knuckle) is the hand's natural center
                    # for octave-band tracking; using the wrist forced the user
                    # to overreach to the top of the frame. Octave bands are
                    # intrinsically screen-space so we keep this 2D regardless
                    # of the pinch-math path.
                    hand_y = landmarks[MIDDLE_FINGER_MCP].y
                    current_band = selector.update(hand_y)

                    # Pinch math runs on 3D world coordinates when available
                    # and the user has not opted out. 2D is the fallback.
                    use_3d = tunables.use_3d_pinches and world is not None

                    for finger in ALL_FINGERS:
                        if use_3d:
                            d = normalized_pinch_distance_3d(world, finger)
                        else:
                            d = normalized_pinch_distance(landmarks, finger)
                        estimators[finger].add_sample(now, d)
                        event = detectors[finger].update(d)
                        if event is PinchEvent.PINCH_ON:
                            note = resolve_midi_note(
                                spec, cfg.finger_degrees, finger, current_band, selector
                            )
                            velocity = estimators[finger].estimate_velocity()
                            held_notes[finger] = note
                            last_velocity[finger] = velocity
                            synth.note_on(note, velocity)
                            recorder.record_note_on(now, note, velocity)
                        elif event is PinchEvent.PINCH_OFF:
                            note = held_notes.pop(finger, None)
                            if note is not None:
                                synth.note_off(note)
                                recorder.record_note_off(time.perf_counter(), note)
                        distances[finger] = d
                        pinched[finger] = detectors[finger].is_pinched

                    draw_hand(frame, landmarks)
                    draw_pinch_indicators(frame, landmarks, pinched, distances)
                    draw_velocity_readout(frame, pinched, last_velocity)

                if modulation_hand is not None:
                    mod_y = modulation_hand.landmarks[MIDDLE_FINGER_MCP].y
                    cc_value = modulator.compute_value(mod_y)
                    if (now - last_cc_send_time) >= modulator.update_interval_s \
                            and modulator.should_emit(cc_value):
                        synth.control_change(modulator.cc_number, cc_value)
                        recorder.record_control_change(now, modulator.cc_number, cc_value)
                        modulator.mark_sent(cc_value)
                        last_cc_send_time = now
                    draw_modulation_hand(frame, modulation_hand.landmarks)
                else:
                    # Modulation hand left frame; drop the smoothing state so
                    # the next entry starts fresh rather than from a stale value.
                    modulator.reset()

                draw_octave_bands(frame, selector.boundaries, current_band)
                draw_scale_readout(frame, spec, selector.octave_for_band(current_band))
                draw_instrument_readout(frame, synth.program)
                draw_rec_indicator(frame, recorder.is_recording, recorder.event_count)
                draw_cc_bar(frame, modulator.cc_number, modulator.last_sent)

                # Rolling FPS over ~30 frames so the readout is not jittery.
                frame_count += 1
                if frame_count >= 30:
                    elapsed = time.perf_counter() - fps_window_start
                    fps = frame_count / elapsed if elapsed > 0 else 0.0
                    frame_count = 0
                    fps_window_start = time.perf_counter()
                draw_fps(frame, fps)
                draw_help(frame)

                cv2.imshow(WINDOW_TITLE, frame)
                action = resolve_hotkey(cv2.waitKey(1) & 0xFF)
                if action.type is ActionType.QUIT:
                    logger.info("Quit requested")
                    break
                elif action.type is ActionType.RECORD_TOGGLE:
                    _toggle_recording(recorder, synth, time.perf_counter())
                elif action.type is ActionType.INSTRUMENT_PREV:
                    synth.change_instrument(synth.program - 1)
                    recorder.record_program_change(time.perf_counter(), synth.program)
                elif action.type is ActionType.INSTRUMENT_NEXT:
                    synth.change_instrument(synth.program + 1)
                    recorder.record_program_change(time.perf_counter(), synth.program)
                elif action.type is ActionType.SET_KEY:
                    spec = ScaleSpec(key=action.payload, scale_name=spec.scale_name)
                    logger.info("Key set to %s", spec.key)
                elif action.type is ActionType.SET_SCALE:
                    spec = ScaleSpec(key=spec.key, scale_name=action.payload)
                    logger.info("Scale set to %s", spec.scale_name)
                elif action.type is ActionType.OPEN_SETTINGS:
                    new_tunables = open_settings_panel(
                        tunables, CONFIG_PATH, CONFIG_EXAMPLE_PATH
                    )
                    if new_tunables is not None:
                        _apply_tunables(new_tunables, tunables, detectors, estimators)
        finally:
            # Stop and save any active recording before tearing down.
            if recorder.is_recording:
                recorder.stop()
            # Release every still-held note so the synth does not hang.
            for finger, note in held_notes.items():
                synth.note_off(note)
            cap.release()
            cv2.destroyAllWindows()

    return 0


def _toggle_recording(recorder: MidiRecorder, synth: Synth, now: float) -> None:
    """Start or stop the recorder based on its current state."""
    if recorder.is_recording:
        path = recorder.stop()
        if path is not None:
            logger.info("Recording saved to %s", path)
    else:
        recorder.start(now, synth.program)


def _apply_tunables(
    new: TunableSettings,
    live: TunableSettings,
    detectors: dict[Finger, PinchDetector],
    estimators: dict[Finger, VelocityEstimator],
) -> None:
    """Push panel-edited settings into the running state.

    Detectors keep their pinched/released state across the threshold
    change so a held note does not jump off. Velocity estimators get
    only the closure-rate update; their sample buffer is preserved.
    """
    live.pinch_thresholds_2d = dict(new.pinch_thresholds_2d)
    live.use_3d_pinches = new.use_3d_pinches
    live.pinch_threshold_3d = new.pinch_threshold_3d
    live.pinch_release_3d = new.pinch_release_3d
    live.fast_closure_rate = new.fast_closure_rate

    if live.use_3d_pinches:
        for det in detectors.values():
            det.set_thresholds(live.pinch_threshold_3d, live.pinch_release_3d)
        logger.info(
            "Settings applied: pinch=3D on=%.3f off=%.3f, fast_closure_rate=%.2f",
            live.pinch_threshold_3d, live.pinch_release_3d, live.fast_closure_rate,
        )
    else:
        for finger, det in detectors.items():
            on, off = live.pinch_thresholds_2d[finger]
            det.set_thresholds(on, off)
        per_finger = " ".join(
            f"{f.value}={live.pinch_thresholds_2d[f][0]:.2f}/"
            f"{live.pinch_thresholds_2d[f][1]:.2f}"
            for f in ALL_FINGERS
        )
        logger.info(
            "Settings applied: pinch=2D [%s], fast_closure_rate=%.2f",
            per_finger, live.fast_closure_rate,
        )
    for est in estimators.values():
        est.set_fast_closure_rate(live.fast_closure_rate)


def _classify_hands(
    hands: list[TrackedHand],
    playing_hand_setting: str,
    dominant_hand: str,
) -> tuple[TrackedHand | None, TrackedHand | None]:
    """Decide which detected hand plays notes and which modulates.

    Returns (playing_hand, modulation_hand), either of which can be None.

    Logic:
    - If only one hand is detected, it is the playing hand (regardless
      of which side it is on); modulation is off.
    - With two hands, the setting decides:
        auto: trust MediaPipe handedness, fall back to dominant_hand on
              ambiguous labels (e.g. both labeled the same)
        right / left: that side plays, the other modulates
    - MediaPipe handedness is reported from the camera's anatomical
      perspective on the un-mirrored image. Because we mirror the frame
      for display, we invert the label: a hand MediaPipe calls "Right"
      shows up on the user's LEFT side of the screen, which corresponds
      to the user's LEFT hand. So invert to get the user's perspective.
    """
    if not hands:
        return None, None
    if len(hands) == 1:
        return hands[0], None

    # Two hands. Compute each hand's user-perspective label.
    def user_side(h: TrackedHand) -> str:
        # MediaPipe Right -> user's Left after mirror, and vice versa.
        return "left" if h.handedness == "Right" else "right"

    user_sides = [user_side(h) for h in hands]
    target_side = playing_hand_setting if playing_hand_setting in ("right", "left") else dominant_hand

    # If user_sides has both 'right' and 'left', pick by target_side.
    if "right" in user_sides and "left" in user_sides:
        playing_idx = user_sides.index(target_side)
        modulation_idx = 1 - playing_idx
        return hands[playing_idx], hands[modulation_idx]

    # Ambiguous: both hands labeled the same. Fall back to picking the
    # higher-confidence one as the playing hand.
    higher = max(range(2), key=lambda i: hands[i].handedness_score)
    other = 1 - higher
    return hands[higher], hands[other]


if __name__ == "__main__":
    sys.exit(main())

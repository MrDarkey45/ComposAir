"""ComposAir entry point.

Phase 4: webcam -> hand tracking -> 4-way pinch detection -> note
resolved from active key + scale + scale degree + octave band. Velocity
is derived from how fast you close the pinch (gesture speed). Press Q
to quit.

Run from the project root:
    python -m composair.main
"""

from __future__ import annotations

import logging
import sys
import time

import cv2

from .config import load_config
from .gestures import (
    ALL_FINGERS,
    Finger,
    MIDDLE_FINGER_MCP,
    PinchDetector,
    PinchEvent,
    Point2D,
    VelocityEstimator,
    normalized_pinch_distance,
)
from .mapping import OctaveBandSelector, resolve_midi_note
from .scales import ScaleSpec
from .synth import Synth
from .tracker import HandTracker
from .ui import (
    draw_fps,
    draw_hand,
    draw_help,
    draw_octave_bands,
    draw_pinch_indicators,
    draw_scale_readout,
    draw_velocity_readout,
)

WINDOW_TITLE = "ComposAir"

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
    # independently; same thresholds and velocity config.
    detectors: dict[Finger, PinchDetector] = {
        finger: PinchDetector(on_threshold=cfg.pinch_threshold,
                              off_threshold=cfg.pinch_release)
        for finger in ALL_FINGERS
    }
    estimators: dict[Finger, VelocityEstimator] = {
        finger: VelocityEstimator(cfg.velocity) for finger in ALL_FINGERS
    }
    selector = OctaveBandSelector(cfg.octave_bands)
    spec = ScaleSpec(key=cfg.key, scale_name=cfg.scale)

    # MIDI note that each currently-held finger committed to at note-on,
    # so note-off sends the matching value even if the hand has moved bands.
    held_notes: dict[Finger, int] = {}
    # Most recent velocity resolved per finger, for the UI readout.
    last_velocity: dict[Finger, int] = {}

    with Synth(soundfont=cfg.soundfont, instrument=cfg.instrument,
               audio_driver=cfg.audio_driver, sample_rate=cfg.sample_rate) as synth, \
         HandTracker(num_hands=1) as tracker:

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

                if hands:
                    landmarks = hands[0]
                    # Use middle-finger MCP (knuckle) as the hand's "center" so the
                    # user doesn't have to lift their whole arm to reach the top
                    # octave band. More natural reach.
                    hand_y = landmarks[MIDDLE_FINGER_MCP].y
                    current_band = selector.update(hand_y)
                    now = time.perf_counter()

                    for finger in ALL_FINGERS:
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
                        elif event is PinchEvent.PINCH_OFF:
                            note = held_notes.pop(finger, None)
                            if note is not None:
                                synth.note_off(note)
                        distances[finger] = d
                        pinched[finger] = detectors[finger].is_pinched

                    draw_hand(frame, landmarks)
                    draw_pinch_indicators(frame, landmarks, pinched, distances)
                    draw_velocity_readout(frame, pinched, last_velocity)

                draw_octave_bands(frame, selector.boundaries, current_band)
                draw_scale_readout(frame, spec, selector.octave_for_band(current_band))

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
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    logger.info("Quit requested")
                    break
        finally:
            # Release every still-held note so the synth does not hang.
            for finger, note in held_notes.items():
                synth.note_off(note)
            cap.release()
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())

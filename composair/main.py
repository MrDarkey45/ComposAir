"""ComposAir entry point.

Phase 2: webcam -> hand tracking -> 4-way pinch detection (thumb to
index/middle/ring/pinky) -> each finger plays its own fixed MIDI note.
Press Q to quit.

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
    PinchDetector,
    PinchEvent,
    normalized_pinch_distance,
)
from .synth import Synth
from .tracker import HandTracker
from .ui import draw_fps, draw_hand, draw_help, draw_pinch_indicators

# Velocity stays fixed until Phase 4 derives it from gesture speed.
PHASE2_VELOCITY = 100
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

    # One detector per finger so they fire independently; same thresholds.
    detectors: dict[Finger, PinchDetector] = {
        finger: PinchDetector(on_threshold=cfg.pinch_threshold,
                              off_threshold=cfg.pinch_release)
        for finger in ALL_FINGERS
    }

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

                # Per-frame snapshot of distances and pinch state, used by the UI.
                distances: dict[Finger, float] = {}
                pinched: dict[Finger, bool] = {}

                if hands:
                    landmarks = hands[0]
                    for finger in ALL_FINGERS:
                        d = normalized_pinch_distance(landmarks, finger)
                        event = detectors[finger].update(d)
                        if event is PinchEvent.PINCH_ON:
                            synth.note_on(cfg.finger_notes[finger], PHASE2_VELOCITY)
                        elif event is PinchEvent.PINCH_OFF:
                            synth.note_off(cfg.finger_notes[finger])
                        distances[finger] = d
                        pinched[finger] = detectors[finger].is_pinched

                    draw_hand(frame, landmarks)
                    draw_pinch_indicators(frame, landmarks, pinched, distances)

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
            for finger, det in detectors.items():
                if det.is_pinched:
                    synth.note_off(cfg.finger_notes[finger])
            cap.release()
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""ComposAir entry point.

Phase 1: webcam -> hand tracking -> pinch detection (thumb + index only)
-> play a fixed MIDI note (middle C). Press Q to quit.

Run from the project root:
    python -m composair.main
"""

from __future__ import annotations

import logging
import sys
import time

import cv2

from .config import load_config
from .gestures import PinchDetector, PinchEvent, normalized_pinch_distance
from .synth import Synth
from .tracker import HandTracker
from .ui import draw_fps, draw_hand, draw_help, draw_pinch_indicator

# Phase 1 plays a single fixed note. Phase 3 makes this scale-driven.
PHASE1_NOTE = 60       # middle C
PHASE1_VELOCITY = 100
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

    detector = PinchDetector(on_threshold=cfg.pinch_threshold,
                             off_threshold=cfg.pinch_release)

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

                if hands:
                    landmarks = hands[0]
                    distance = normalized_pinch_distance(landmarks)
                    event = detector.update(distance)
                    if event is PinchEvent.PINCH_ON:
                        synth.note_on(PHASE1_NOTE, PHASE1_VELOCITY)
                    elif event is PinchEvent.PINCH_OFF:
                        synth.note_off(PHASE1_NOTE)

                    draw_hand(frame, landmarks)
                    draw_pinch_indicator(frame, landmarks, detector.is_pinched, distance)

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
            if detector.is_pinched:
                synth.note_off(PHASE1_NOTE)
            cap.release()
            cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    sys.exit(main())

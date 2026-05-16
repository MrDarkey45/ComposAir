"""MediaPipe HandLandmarker wrapper.

Uses the Tasks API (not the deprecated solutions.hands). Configured for
LIVE_STREAM mode which is async and lowest-latency on real-time webcam
input. Returns the most recent result on demand.

Now returns both landmarks and a handedness label per hand so the main
loop can route the playing hand and modulation hand independently.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

import mediapipe as mp
import numpy as np

from .gestures import Point2D

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"


@dataclass(frozen=True)
class TrackedHand:
    """A single detected hand: 21 landmarks plus a handedness label.

    Handedness is the label MediaPipe reports for this hand: "Left" or
    "Right". Note that MediaPipe labels from the user's anatomical
    perspective on the original (un-mirrored) image. Callers that flip
    the frame for display should invert this label, or do that flip
    upstream before submitting frames.
    """

    landmarks: list[Point2D]
    handedness: str  # "Left" or "Right"
    handedness_score: float  # confidence 0-1


class HandTracker:
    """Multi-hand tracker. Default 2 hands so the modulation hand can be detected."""

    def __init__(
        self,
        num_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"HandLandmarker model not found at {MODEL_PATH}. "
                "Download it before running (see README)."
            )

        base_options = mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH))
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.LIVE_STREAM,
            num_hands=num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_presence_confidence,
            min_tracking_confidence=min_tracking_confidence,
            result_callback=self._on_result,
        )

        self._landmarker = mp.tasks.vision.HandLandmarker.create_from_options(options)
        self._latest: list[TrackedHand] | None = None
        self._lock = Lock()
        self._t0 = time.perf_counter()
        logger.info("HandLandmarker ready (num_hands=%d)", num_hands)

    def _on_result(self, result, output_image, timestamp_ms: int) -> None:
        # MediaPipe parallel arrays: result.hand_landmarks[i] and
        # result.handedness[i] correspond to the same detected hand.
        hands: list[TrackedHand] = []
        for hand_landmarks, handedness in zip(result.hand_landmarks, result.handedness):
            # handedness is a list of Category objects; the top one is the
            # model's best label for this hand.
            top = handedness[0] if handedness else None
            label = top.category_name if top is not None else "Right"
            score = float(top.score) if top is not None else 0.0
            hands.append(TrackedHand(
                landmarks=[Point2D(lm.x, lm.y) for lm in hand_landmarks],
                handedness=label,
                handedness_score=score,
            ))
        with self._lock:
            self._latest = hands

    def submit_frame(self, frame_bgr: np.ndarray) -> None:
        """Send a BGR frame for async processing. Non-blocking."""
        # MediaPipe expects RGB and a monotonic timestamp in ms.
        rgb = frame_bgr[:, :, ::-1].copy()
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms = int((time.perf_counter() - self._t0) * 1000)
        self._landmarker.detect_async(mp_image, ts_ms)

    def latest_hands(self) -> list[TrackedHand]:
        """Return the most recent set of hands (possibly empty). Thread-safe."""
        with self._lock:
            return list(self._latest) if self._latest else []

    def close(self) -> None:
        logger.info("Closing HandLandmarker")
        self._landmarker.close()

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ARG002
        del exc_type, exc_val, exc_tb
        self.close()
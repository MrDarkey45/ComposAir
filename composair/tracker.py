"""MediaPipe HandLandmarker wrapper.

Uses the Tasks API (not the deprecated solutions.hands). Configured for
LIVE_STREAM mode which is async and lowest-latency on real-time webcam
input. Returns the most recent result on demand.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Lock

import mediapipe as mp
import numpy as np

from .gestures import Point2D

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "hand_landmarker.task"


class HandTracker:
    """Single-hand tracker; later phases will raise num_hands to 2."""

    def __init__(
        self,
        num_hands: int = 1,
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
        self._latest: list[list[Point2D]] | None = None
        self._lock = Lock()
        self._t0 = time.perf_counter()
        logger.info("HandLandmarker ready (num_hands=%d)", num_hands)

    def _on_result(self, result, output_image, timestamp_ms: int) -> None:
        # Convert MediaPipe NormalizedLandmark to our Point2D dataclass so
        # downstream code is not coupled to the mediapipe type system.
        hands: list[list[Point2D]] = []
        for hand_landmarks in result.hand_landmarks:
            hands.append([Point2D(lm.x, lm.y) for lm in hand_landmarks])
        with self._lock:
            self._latest = hands

    def submit_frame(self, frame_bgr: np.ndarray) -> None:
        """Send a BGR frame for async processing. Non-blocking."""
        # MediaPipe expects RGB and a monotonic timestamp in ms.
        rgb = frame_bgr[:, :, ::-1].copy()
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms = int((time.perf_counter() - self._t0) * 1000)
        self._landmarker.detect_async(mp_image, ts_ms)

    def latest_hands(self) -> list[list[Point2D]]:
        """Return the most recent set of hands (possibly empty). Thread-safe."""
        with self._lock:
            return list(self._latest) if self._latest else []

    def close(self) -> None:
        logger.info("Closing HandLandmarker")
        self._landmarker.close()

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

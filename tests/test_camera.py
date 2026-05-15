"""Smoke test: open the webcam, confirm it streams, show 60 frames, then exit.

Run from the project root:
    .venv\\Scripts\\python.exe tests\\test_camera.py
"""

from __future__ import annotations

import sys
import time

import cv2

CAMERA_INDEX = 0
WIDTH = 1280
HEIGHT = 720
TARGET_FPS = 30
FRAMES_TO_SHOW = 60  # ~2 seconds at 30 FPS


def main() -> int:
    print(f"OpenCV version: {cv2.__version__}")
    print(f"Opening camera {CAMERA_INDEX} via DirectShow ({WIDTH}x{HEIGHT} @ {TARGET_FPS} FPS)...")

    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("ERROR: could not open camera. Is it in use by another app?", file=sys.stderr)
        return 1

    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)

    actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    print(f"Camera reports: {actual_w}x{actual_h} @ {actual_fps:.1f} FPS")

    frames = 0
    start = time.perf_counter()
    while frames < FRAMES_TO_SHOW:
        ok, frame = cap.read()
        if not ok:
            print(f"ERROR: frame {frames} read failed", file=sys.stderr)
            cap.release()
            cv2.destroyAllWindows()
            return 1

        cv2.putText(
            frame,
            f"Frame {frames + 1}/{FRAMES_TO_SHOW} - press Q to quit early",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
        cv2.imshow("ComposAir camera smoke test", frame)
        frames += 1

        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("User quit early.")
            break

    elapsed = time.perf_counter() - start
    measured_fps = frames / elapsed if elapsed > 0 else 0.0

    cap.release()
    cv2.destroyAllWindows()

    print(f"Captured {frames} frames in {elapsed:.2f}s ({measured_fps:.1f} FPS measured)")
    print("OK - camera works.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Load ComposAir configuration from config.yaml into a typed dataclass.

The config file is expected at the project root. If config.yaml does not
exist, falls back to config.example.yaml so the app still runs out of the box.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from .gestures import Finger

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
CONFIG_EXAMPLE_PATH = PROJECT_ROOT / "config.example.yaml"


@dataclass(frozen=True)
class Config:
    """Resolved ComposAir configuration."""

    # Audio / synth
    soundfont: Path
    instrument: int
    audio_driver: str
    sample_rate: int

    # Camera
    camera_index: int
    camera_width: int
    camera_height: int
    camera_fps: int

    # Gesture detection
    pinch_threshold: float
    pinch_release: float

    # Note assignments: which MIDI note each finger plays
    finger_notes: dict[Finger, int]

    # Musical state (used from Phase 3 on; loaded now so config schema is stable)
    key: str
    scale: str


def load_config() -> Config:
    """Read config.yaml (or config.example.yaml as fallback) and return a Config."""
    if CONFIG_PATH.exists():
        path = CONFIG_PATH
    elif CONFIG_EXAMPLE_PATH.exists():
        logger.warning("config.yaml not found, falling back to config.example.yaml")
        path = CONFIG_EXAMPLE_PATH
    else:
        raise FileNotFoundError(
            f"No config file found. Expected one of: {CONFIG_PATH}, {CONFIG_EXAMPLE_PATH}"
        )

    logger.info("Loading config from %s", path)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    soundfont_path = (PROJECT_ROOT / data["soundfont"]).resolve()
    finger_notes = _parse_finger_notes(data["finger_notes"])

    return Config(
        soundfont=soundfont_path,
        instrument=int(data["instrument"]),
        audio_driver=str(data["audio_driver"]),
        sample_rate=int(data["sample_rate"]),
        camera_index=int(data["camera_index"]),
        camera_width=int(data["camera_width"]),
        camera_height=int(data["camera_height"]),
        camera_fps=int(data["camera_fps"]),
        pinch_threshold=float(data["pinch_threshold"]),
        pinch_release=float(data["pinch_release"]),
        finger_notes=finger_notes,
        key=str(data["key"]),
        scale=str(data["scale"]),
    )


def _parse_finger_notes(raw: dict[str, object]) -> dict[Finger, int]:
    """Convert the YAML mapping {finger_name: midi_note} into a typed dict.

    Validates that all four fingers are present and every note is in 0-127.
    """
    parsed: dict[Finger, int] = {}
    for finger in Finger:
        if finger.value not in raw:
            raise ValueError(f"finger_notes missing entry for '{finger.value}'")
        note = int(raw[finger.value])  # type: ignore[arg-type]
        if not 0 <= note <= 127:
            raise ValueError(
                f"finger_notes['{finger.value}'] = {note} is outside MIDI range 0-127"
            )
        parsed[finger] = note
    return parsed

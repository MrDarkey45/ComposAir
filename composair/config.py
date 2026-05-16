"""Load ComposAir configuration from config.yaml into a typed dataclass.

The config file is expected at the project root. If config.yaml does not
exist, falls back to config.example.yaml so the app still runs out of the box.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from .gestures import Finger, VelocityConfig
from .mapping import BandSelectorConfig
from .modulation import ModulationConfig
from .scales import KEY_OFFSETS, SCALES

# Accepted values for the playing_hand setting.
_PLAYING_HAND_OPTIONS = ("auto", "right", "left")
_DOMINANT_HAND_OPTIONS = ("right", "left")

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

    # Musical state
    key: str
    scale: str

    # Scale-degree assignment per finger (1-indexed; 1 = root)
    finger_degrees: dict[Finger, int]

    # Octave band selection (controls how hand Y position maps to octave)
    octave_bands: BandSelectorConfig

    # Gesture-speed -> MIDI velocity mapping
    velocity: VelocityConfig

    # Second-hand modulation
    modulation: ModulationConfig
    playing_hand: str        # auto, right, or left
    dominant_hand: str       # right or left


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
    finger_degrees = _parse_finger_degrees(data["finger_degrees"])
    key = _validate_key(str(data["key"]))
    scale = _validate_scale(str(data["scale"]))
    octave_bands = _parse_octave_bands(data["octave_bands"])
    velocity = _parse_velocity(data["velocity"])
    modulation, playing_hand, dominant_hand = _parse_modulation(data["modulation"])

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
        key=key,
        scale=scale,
        finger_degrees=finger_degrees,
        octave_bands=octave_bands,
        velocity=velocity,
        modulation=modulation,
        playing_hand=playing_hand,
        dominant_hand=dominant_hand,
    )


def _parse_finger_degrees(raw: dict[str, object]) -> dict[Finger, int]:
    """Convert the YAML mapping {finger_name: scale_degree} into a typed dict.

    Validates that all four fingers are present and degrees are >= 1.
    """
    parsed: dict[Finger, int] = {}
    for finger in Finger:
        if finger.value not in raw:
            raise ValueError(f"finger_degrees missing entry for '{finger.value}'")
        degree = int(raw[finger.value])  # type: ignore[arg-type]
        if degree < 1:
            raise ValueError(
                f"finger_degrees['{finger.value}'] = {degree} must be >= 1"
            )
        parsed[finger] = degree
    return parsed


def _validate_key(key: str) -> str:
    if key not in KEY_OFFSETS:
        raise ValueError(
            f"unknown key '{key}'. Supported: {', '.join(sorted(KEY_OFFSETS))}"
        )
    return key


def _validate_scale(scale: str) -> str:
    if scale not in SCALES:
        raise ValueError(
            f"unknown scale '{scale}'. Supported: {', '.join(sorted(SCALES))}"
        )
    return scale


def _parse_octave_bands(raw: dict[str, object]) -> BandSelectorConfig:
    return BandSelectorConfig(
        num_bands=int(raw["count"]),  # type: ignore[arg-type]
        base_octave=int(raw["base_octave"]),  # type: ignore[arg-type]
        hysteresis=float(raw["hysteresis"]),  # type: ignore[arg-type]
    )


def _parse_velocity(raw: dict[str, object]) -> VelocityConfig:
    return VelocityConfig(
        min_velocity=int(raw["min"]),  # type: ignore[arg-type]
        max_velocity=int(raw["max"]),  # type: ignore[arg-type]
        default=int(raw["default"]),  # type: ignore[arg-type]
        window_ms=float(raw["window_ms"]),  # type: ignore[arg-type]
        fast_closure_rate=float(raw["fast_closure_rate"]),  # type: ignore[arg-type]
    )


def _parse_modulation(raw: dict[str, object]) -> tuple[ModulationConfig, str, str]:
    """Return (ModulationConfig, playing_hand, dominant_hand)."""
    playing_hand = str(raw["playing_hand"]).lower()
    if playing_hand not in _PLAYING_HAND_OPTIONS:
        raise ValueError(
            f"modulation.playing_hand must be one of "
            f"{_PLAYING_HAND_OPTIONS}, got '{playing_hand}'"
        )
    dominant_hand = str(raw["dominant_hand"]).lower()
    if dominant_hand not in _DOMINANT_HAND_OPTIONS:
        raise ValueError(
            f"modulation.dominant_hand must be one of "
            f"{_DOMINANT_HAND_OPTIONS}, got '{dominant_hand}'"
        )
    cfg = ModulationConfig(
        cc_number=int(raw["cc_number"]),  # type: ignore[arg-type]
        smoothing=float(raw["smoothing"]),  # type: ignore[arg-type]
        deadzone=int(raw["deadzone"]),  # type: ignore[arg-type]
        update_interval_ms=float(raw["update_interval_ms"]),  # type: ignore[arg-type]
    )
    return cfg, playing_hand, dominant_hand

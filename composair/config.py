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
from .smoothing import SmoothingConfig

# Accepted values for the playing_hand setting.
_PLAYING_HAND_OPTIONS = ("auto", "right", "left")
_DOMINANT_HAND_OPTIONS = ("right", "left")

logger = logging.getLogger(__name__)

from .paths import resource_root

PROJECT_ROOT = resource_root()
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

    # 2D pinch thresholds per finger for the playing hand: {Finger: (on, off)}.
    # MediaPipe accuracy is not uniform across the hand; per-finger tuning
    # is the right level of granularity for live retuning.
    pinch_thresholds_2d: dict[Finger, tuple[float, float]]

    # 2D pinch thresholds per finger for the modulation (transport) hand.
    # Separate from the playing hand because the non-dominant hand typically
    # pinches with different ergonomics. If absent from config, falls back
    # to pinch_thresholds_2d at load time so older configs still load.
    transport_thresholds_2d: dict[Finger, tuple[float, float]]

    # 3D pinch detection (world-space landmarks; preferred for occlusion-robustness)
    use_3d_pinches: bool
    pinch_threshold_3d: float
    pinch_release_3d: float

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

    # Landmark smoothing
    smoothing: SmoothingConfig


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
    smoothing = _parse_smoothing(data["smoothing"])

    return Config(
        soundfont=soundfont_path,
        instrument=int(data["instrument"]),
        audio_driver=str(data["audio_driver"]),
        sample_rate=int(data["sample_rate"]),
        camera_index=int(data["camera_index"]),
        camera_width=int(data["camera_width"]),
        camera_height=int(data["camera_height"]),
        camera_fps=int(data["camera_fps"]),
        pinch_thresholds_2d=_parse_pinch_thresholds_2d(data, key="pinch_thresholds"),
        transport_thresholds_2d=_parse_pinch_thresholds_2d(
            data, key="transport_thresholds", fallback_key="pinch_thresholds"
        ),
        use_3d_pinches=bool(data.get("use_3d_pinches", True)),
        pinch_threshold_3d=float(data.get("pinch_threshold_3d", 0.50)),
        pinch_release_3d=float(data.get("pinch_release_3d", 0.65)),
        key=key,
        scale=scale,
        finger_degrees=finger_degrees,
        octave_bands=octave_bands,
        velocity=velocity,
        modulation=modulation,
        playing_hand=playing_hand,
        dominant_hand=dominant_hand,
        smoothing=smoothing,
    )


def _parse_pinch_thresholds_2d(
    data: dict[str, object],
    key: str = "pinch_thresholds",
    fallback_key: str | None = None,
) -> dict[Finger, tuple[float, float]]:
    """Read 2D pinch thresholds with backwards compatibility.

    The function is parameterized on the YAML key so both the playing-hand
    thresholds ("pinch_thresholds") and the transport-hand thresholds
    ("transport_thresholds") can share the parser.

    Fallback chain:
    1. Try the requested `key` as a per-finger map.
    2. If absent and a `fallback_key` is supplied, try that as a per-finger
       map (used so transport falls back to playing-hand values when the
       user has not customized transport yet).
    3. Final fallback: legacy universal `pinch_threshold`/`pinch_release`.
    """
    per_finger = data.get(key)
    if per_finger is None and fallback_key is not None:
        per_finger = data.get(fallback_key)
    if isinstance(per_finger, dict):
        out: dict[Finger, tuple[float, float]] = {}
        for finger in Finger:
            entry = per_finger.get(finger.value)
            if not isinstance(entry, dict):
                raise ValueError(
                    f"{key} missing finger '{finger.value}' "
                    f"or value is not a mapping"
                )
            # Accept new (trigger/release) plus two legacy variants of
            # on/off: booleans True/False (from unquoted YAML 1.1 keys)
            # and the literal strings "on"/"off" (from quoted-key configs
            # written by an earlier panel before this fix). The canonical
            # schema is trigger/release.
            trigger = entry.get("trigger")
            release = entry.get("release")
            if trigger is None and True in entry:
                trigger = entry[True]
            if release is None and False in entry:
                release = entry[False]
            if trigger is None and "on" in entry:
                trigger = entry["on"]
            if release is None and "off" in entry:
                release = entry["off"]
            if trigger is None or release is None:
                raise ValueError(
                    f"{key}['{finger.value}']: "
                    f"missing 'trigger' or 'release' key"
                )
            on = float(trigger)
            off = float(release)
            if on >= off:
                raise ValueError(
                    f"{key}['{finger.value}']: "
                    f"trigger ({on}) must be < release ({off})"
                )
            out[finger] = (on, off)
        return out

    # Legacy: single pair applied to all four fingers.
    on = float(data.get("pinch_threshold", 0.18))
    off = float(data.get("pinch_release", 0.23))
    if on >= off:
        raise ValueError(f"pinch_threshold ({on}) must be < pinch_release ({off})")
    return {finger: (on, off) for finger in Finger}


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


def _parse_smoothing(raw: dict[str, object]) -> SmoothingConfig:
    return SmoothingConfig(
        enabled=bool(raw["enabled"]),
        min_cutoff=float(raw["min_cutoff"]),  # type: ignore[arg-type]
        beta=float(raw["beta"]),  # type: ignore[arg-type]
        d_cutoff=float(raw["d_cutoff"]),  # type: ignore[arg-type]
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

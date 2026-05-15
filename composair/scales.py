"""Music scale theory.

A Scale is an ordered tuple of semitone offsets from the root, covering one
octave (e.g. major = (0, 2, 4, 5, 7, 9, 11)). A Key is a root note name
plus its semitone offset from C. The scale_degree_to_midi function combines
key, scale, octave, and degree into a MIDI note number.

Scale degrees are 1-indexed for musical familiarity: degree 1 is the root,
degree 3 is the third, etc. Degrees outside the scale wrap around with the
appropriate octave offset, so degree 8 in C major is C5 (one octave above
degree 1 / C4).
"""

from __future__ import annotations

from dataclasses import dataclass

# Semitone offsets within one octave, 1-indexed-friendly.
# (Internal storage is 0-indexed for clean modulo math.)
SCALES: dict[str, tuple[int, ...]] = {
    "major":            (0, 2, 4, 5, 7, 9, 11),
    "natural_minor":    (0, 2, 3, 5, 7, 8, 10),
    "harmonic_minor":   (0, 2, 3, 5, 7, 8, 11),
    "dorian":           (0, 2, 3, 5, 7, 9, 10),
    "major_pentatonic": (0, 2, 4, 7, 9),
    "minor_pentatonic": (0, 3, 5, 7, 10),
}

# Key letter to semitone offset from C. Supports sharp accidentals via "C#",
# "F#" etc.; flats are not first-class to keep the config schema simple.
KEY_OFFSETS: dict[str, int] = {
    "C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
    "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11,
}

# C4 (middle C) is MIDI 60. We treat "octave 4" as the band whose root is C4.
MIDI_C0 = 12


@dataclass(frozen=True)
class ScaleSpec:
    """Resolved key + scale, ready to convert degrees to MIDI notes."""

    key: str            # e.g. "C", "F#"
    scale_name: str     # e.g. "major"

    @property
    def root_offset(self) -> int:
        return KEY_OFFSETS[self.key]

    @property
    def intervals(self) -> tuple[int, ...]:
        return SCALES[self.scale_name]

    @property
    def length(self) -> int:
        """Number of degrees in one octave of this scale (5 for pentatonic, 7 for diatonic)."""
        return len(self.intervals)


def scale_degree_to_midi(spec: ScaleSpec, degree: int, octave: int) -> int:
    """Resolve a 1-indexed scale degree at a given octave to a MIDI note.

    Degrees beyond the scale length wrap into the next octave, so for a
    7-note scale: degree 1 -> octave N, degree 8 -> octave N+1 at degree 1,
    degree 15 -> octave N+2 at degree 1. Degrees less than 1 are not
    supported (raise ValueError) since the rest of the app never produces them.
    """
    if degree < 1:
        raise ValueError(f"scale degree must be >= 1, got {degree}")
    intervals = spec.intervals
    length = spec.length
    # Convert 1-indexed degree into (zero-indexed within octave, octave delta).
    zero_degree = degree - 1
    octave_delta, in_octave = divmod(zero_degree, length)
    semitone = intervals[in_octave]
    midi = MIDI_C0 + (octave + octave_delta) * 12 + spec.root_offset + semitone
    if not 0 <= midi <= 127:
        raise ValueError(
            f"resolved MIDI note {midi} is outside 0-127 "
            f"(key={spec.key}, scale={spec.scale_name}, degree={degree}, octave={octave})"
        )
    return midi


def list_available_scales() -> tuple[str, ...]:
    """Return the names of every built-in scale, for config validation messages."""
    return tuple(SCALES.keys())


def list_available_keys() -> tuple[str, ...]:
    """Return the names of every supported key, for config validation messages."""
    return tuple(KEY_OFFSETS.keys())

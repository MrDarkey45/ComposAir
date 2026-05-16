"""Tkinter-based runtime settings panel.

Opens in its own window. Lets the user adjust the most commonly-tuned
config values with both sliders and number entries, then either applies
them in place (and writes them back to config.yaml so they survive a
restart) or cancels.

Only fields that can be applied to a running session without a restart
appear here. Settings that require a restart (camera resolution, audio
driver, soundfont path) stay in config.yaml and need to be edited there.
"""

from __future__ import annotations

import logging
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from typing import Callable

import yaml

from .gestures import ALL_FINGERS, Finger

logger = logging.getLogger(__name__)


@dataclass
class TunableSettings:
    """The subset of config that the panel can edit.

    Mutated in place by the panel; the caller applies these back to the
    live Config + writes them to config.yaml.

    pinch_thresholds_2d is a dict per Finger of (on, off) tuples. The
    panel exposes one row per finger per threshold so each finger can
    be tuned independently.
    """

    pinch_thresholds_2d: dict[Finger, tuple[float, float]]
    use_3d_pinches: bool
    pinch_threshold_3d: float
    pinch_release_3d: float
    fast_closure_rate: float


_DECIMALS = 4
_QUANTUM = 10 ** -_DECIMALS  # 0.0001


def _round(v: float) -> float:
    """Round to the display precision so we never store 0.180000000003."""
    return round(v, _DECIMALS)


def _make_row(
    parent: tk.Widget,
    row: int,
    label: str,
    initial: float,
    var_min: float,
    var_max: float,
    on_change: Callable[[float], None],
) -> tuple[tk.DoubleVar, ttk.Scale, ttk.Entry]:
    """Build a labelled row with a slider and a number entry that stay in sync.

    The displayed value is a StringVar formatted to 4 decimal places so
    sliders never produce numbers like 0.18000000000003. The slider feeds
    a separate DoubleVar; we mirror between them on every change.

    Returns (display_var, scale, entry). on_change fires with the rounded
    float after either widget is edited.
    """
    slider_var = tk.DoubleVar(value=_round(initial))
    display_var = tk.StringVar(value=f"{_round(initial):.{_DECIMALS}f}")

    ttk.Label(parent, text=label, anchor="w").grid(
        row=row, column=0, sticky="ew", padx=(10, 5), pady=4
    )

    def _on_slider(_v: str) -> None:
        v = _round(slider_var.get())
        display_var.set(f"{v:.{_DECIMALS}f}")
        on_change(v)

    scale = ttk.Scale(
        parent, from_=var_min, to=var_max, variable=slider_var,
        orient="horizontal", command=_on_slider,
    )
    scale.grid(row=row, column=1, sticky="ew", padx=5, pady=4)

    entry = ttk.Entry(parent, textvariable=display_var, width=9)
    entry.grid(row=row, column=2, sticky="e", padx=(5, 10), pady=4)

    def _entry_commit(_event: object | None = None) -> None:
        try:
            v = float(display_var.get())
        except ValueError:
            # Restore the last good value on bad input.
            display_var.set(f"{_round(slider_var.get()):.{_DECIMALS}f}")
            return
        v = _round(max(var_min, min(var_max, v)))
        slider_var.set(v)
        display_var.set(f"{v:.{_DECIMALS}f}")
        on_change(v)

    entry.bind("<FocusOut>", _entry_commit)
    entry.bind("<Return>", _entry_commit)

    return display_var, scale, entry


def open_settings_panel(
    current: TunableSettings,
    config_path: Path,
    example_config_path: Path,
) -> TunableSettings | None:
    """Show a modal Tkinter window. Returns the new settings on Apply, None on Cancel.

    Blocks the calling thread until the window closes. The audio synth
    and tracker threads keep running, so notes you were holding when you
    pressed the hotkey will continue to ring; the camera preview will
    pause until you close the panel.

    config_path is where Apply writes the merged YAML. example_config_path
    is read as the base when config.yaml does not yet exist, so the saved
    file has all fields with sensible comments.
    """
    root = tk.Tk()
    root.title("ComposAir settings")
    # Sized generously so the Apply / Cancel buttons stay visible even on
    # Windows display scaling >= 125%, which inflates Tkinter layouts.
    # Per-finger 2D adds 8 rows so we want extra vertical space.
    root.geometry("620x620")
    root.minsize(560, 540)
    root.configure(padx=4, pady=4)
    # Bring to front and grab focus so the user does not have to alt-tab
    # to find a panel that opened behind the camera window.
    root.lift()
    root.attributes("-topmost", True)
    root.after_idle(root.attributes, "-topmost", False)
    root.focus_force()

    # Working copy mutated by the slider callbacks. Cancel discards it.
    edited = TunableSettings(
        pinch_thresholds_2d={f: current.pinch_thresholds_2d[f] for f in ALL_FINGERS},
        use_3d_pinches=current.use_3d_pinches,
        pinch_threshold_3d=current.pinch_threshold_3d,
        pinch_release_3d=current.pinch_release_3d,
        fast_closure_rate=current.fast_closure_rate,
    )
    result: dict[str, TunableSettings | None] = {"value": None}

    # Pack the buttons FIRST so they reserve space at the bottom and stay
    # visible even if the body content grows. ttk packs in order: bottom
    # bar pinned, body fills the rest.
    buttons = ttk.Frame(root)
    buttons.pack(fill="x", side="bottom", padx=10, pady=10)

    body = ttk.Frame(root)
    body.pack(fill="both", expand=True)
    body.columnconfigure(1, weight=1)

    ttk.Label(body, text="2D pinch thresholds (per finger)",
              font=("TkDefaultFont", 10, "bold")).grid(
        row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 2)
    )

    # 4 fingers x 2 thresholds = 8 rows. Closures captured by default
    # argument so each row's setter binds to the right finger.
    next_row = 1
    for finger in ALL_FINGERS:
        on_v, off_v = edited.pinch_thresholds_2d[finger]

        def make_on_setter(f: Finger) -> Callable[[float], None]:
            def setter(v: float) -> None:
                cur_on, cur_off = edited.pinch_thresholds_2d[f]
                edited.pinch_thresholds_2d[f] = (v, cur_off)
            return setter

        def make_off_setter(f: Finger) -> Callable[[float], None]:
            def setter(v: float) -> None:
                cur_on, cur_off = edited.pinch_thresholds_2d[f]
                edited.pinch_thresholds_2d[f] = (cur_on, v)
            return setter

        _make_row(body, next_row, f"{finger.value} trigger",
                  on_v, 0.05, 0.30, make_on_setter(finger))
        next_row += 1
        _make_row(body, next_row, f"{finger.value} release",
                  off_v, 0.05, 0.30, make_off_setter(finger))
        next_row += 1

    ttk.Separator(body, orient="horizontal").grid(
        row=next_row, column=0, columnspan=3, sticky="ew", padx=10, pady=8
    )
    next_row += 1

    ttk.Label(body, text="3D pinch detection", font=("TkDefaultFont", 10, "bold")).grid(
        row=next_row, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 2)
    )
    next_row += 1

    use_3d_var = tk.BooleanVar(value=edited.use_3d_pinches)

    def _on_3d_toggle() -> None:
        edited.use_3d_pinches = bool(use_3d_var.get())

    ttk.Checkbutton(body, text="Use 3D world landmarks", variable=use_3d_var,
                    command=_on_3d_toggle).grid(
        row=next_row, column=0, columnspan=2, sticky="w", padx=10, pady=2
    )
    next_row += 1

    _make_row(body, next_row, "3D trigger", edited.pinch_threshold_3d,
              0.20, 0.80, lambda v: setattr(edited, "pinch_threshold_3d", v))
    next_row += 1
    _make_row(body, next_row, "3D release", edited.pinch_release_3d,
              0.20, 0.80, lambda v: setattr(edited, "pinch_release_3d", v))
    next_row += 1

    ttk.Separator(body, orient="horizontal").grid(
        row=next_row, column=0, columnspan=3, sticky="ew", padx=10, pady=8
    )
    next_row += 1

    ttk.Label(body, text="Velocity dynamics", font=("TkDefaultFont", 10, "bold")).grid(
        row=next_row, column=0, columnspan=3, sticky="w", padx=10, pady=(0, 2)
    )
    next_row += 1
    _make_row(body, next_row, "fast closure rate", edited.fast_closure_rate,
              0.5, 5.0, lambda v: setattr(edited, "fast_closure_rate", v))

    # Apply / Cancel buttons live in the `buttons` frame packed above.
    def _on_apply() -> None:
        # Sanity: release must exceed trigger by at least a small gap on
        # every finger, else PinchDetector.set_thresholds raises. Snap if
        # needed rather than rejecting the apply outright.
        for f in ALL_FINGERS:
            on, off = edited.pinch_thresholds_2d[f]
            if off <= on:
                edited.pinch_thresholds_2d[f] = (on, min(0.30, on + 0.02))
        if edited.pinch_release_3d <= edited.pinch_threshold_3d:
            edited.pinch_release_3d = min(0.80, edited.pinch_threshold_3d + 0.05)
        _save_to_yaml(edited, config_path, example_config_path)
        result["value"] = edited
        root.destroy()

    def _on_cancel() -> None:
        root.destroy()

    # Cancel on the far right (least destructive position), Apply just
    # inside so it is the natural primary action.
    cancel_btn = ttk.Button(buttons, text="Cancel", command=_on_cancel)
    cancel_btn.pack(side="right", padx=4)
    apply_btn = ttk.Button(buttons, text="Apply", command=_on_apply)
    apply_btn.pack(side="right", padx=4)
    # Hint that Apply is the default action: Enter triggers it.
    root.bind("<Return>", lambda _e: _on_apply())
    root.bind("<Escape>", lambda _e: _on_cancel())

    root.protocol("WM_DELETE_WINDOW", _on_cancel)
    root.mainloop()

    return result["value"]


def _save_to_yaml(
    edited: TunableSettings, config_path: Path, example_config_path: Path
) -> None:
    """Persist the edited subset back to config.yaml.

    Reads the existing config.yaml (or copies from config.example.yaml if
    config.yaml does not yet exist), updates the relevant keys, and writes
    the merged file back. Preserves any fields not in the panel.
    """
    if config_path.exists():
        source = config_path
    elif example_config_path.exists():
        source = example_config_path
    else:
        logger.warning("Neither %s nor %s exists; cannot save settings",
                       config_path, example_config_path)
        return

    with source.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Write the per-finger map. Drop the legacy universal fields if
    # present so the saved file is the canonical post-7C shape.
    data.pop("pinch_threshold", None)
    data.pop("pinch_release", None)
    data["pinch_thresholds"] = {
        f.value: {"trigger": float(on), "release": float(off)}
        for f, (on, off) in edited.pinch_thresholds_2d.items()
    }
    data["use_3d_pinches"] = bool(edited.use_3d_pinches)
    data["pinch_threshold_3d"] = float(edited.pinch_threshold_3d)
    data["pinch_release_3d"] = float(edited.pinch_release_3d)
    velocity = data.setdefault("velocity", {})
    velocity["fast_closure_rate"] = float(edited.fast_closure_rate)

    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)
    logger.info("Settings saved to %s", config_path)

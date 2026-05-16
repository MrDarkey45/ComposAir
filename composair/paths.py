"""Resolve project resource paths in both dev and frozen-app modes.

In dev (running from a venv), files like soundfonts/GeneralUser-GS.sf2
sit at the project root next to the composair/ package. In a PyInstaller
frozen bundle they ship into _internal/ alongside the exe.

This module exposes a single resource_root() that returns the correct
base directory in either case. Call it instead of hard-coding
Path(__file__).parent.parent.
"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Return the directory that contains soundfonts/, models/, etc.

    Frozen (PyInstaller): sys._MEIPASS points at the unpacked bundle's
        runtime location, which is _internal/ on disk for a onedir build.
    Dev: the project root, two levels up from this file.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller sets _MEIPASS to the bundle's resource dir.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent
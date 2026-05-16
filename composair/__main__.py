"""Entry point so the package can be launched as `python -m composair`
or built into a single exe with PyInstaller.

Bootstrap order matters: pyFluidSynth imports its DLL at module load
time using a hardcoded `C:\\tools\\fluidsynth\\bin` path. When running
from a PyInstaller bundle that path does not exist on the user's
machine, so we synthesize one before any composair import touches the
synth module.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _bootstrap_fluidsynth_path() -> None:
    """Ensure pyFluidSynth can find its DLLs when running from a bundle.

    pyFluidSynth's loader expects C:\\tools\\fluidsynth\\bin to contain
    libfluidsynth-3.dll and friends. In dev that path is a directory
    junction to wherever FluidSynth is installed. In a packaged exe we
    ship the DLLs next to the executable, and we add the bundle's own
    root to PATH plus add_dll_directory so the loader finds them.
    """
    if getattr(sys, "frozen", False):
        # _MEIPASS points at the unpacked resource directory (which on a
        # onedir bundle is _internal/ next to the exe). That is where
        # PyInstaller put the FluidSynth DLLs.
        meipass = getattr(sys, "_MEIPASS", None)
        bundle_dir = Path(meipass) if meipass else Path(sys.executable).resolve().parent
        os.environ["PATH"] = f"{bundle_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(bundle_dir))
            except OSError:
                pass


_bootstrap_fluidsynth_path()

# Absolute import works in both modes: `python -m composair` puts the
# package on sys.path, and PyInstaller's frozen entry script runs without
# a parent package context (relative imports would fail).
from composair.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
# PyInstaller spec for ComposAir.
#
# Usage:
#   pyinstaller composair.spec --clean --noconfirm
#
# Output:
#   dist/composair/composair.exe  (plus a bundle of DLLs and data files)
#
# We build a "onedir" distribution rather than "onefile" because MediaPipe
# loads its model file from disk at runtime; a onefile build extracts to
# a temp dir on every launch and slows startup. A folder distribution
# also lets the user inspect what shipped (DLLs, SoundFont, model).

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# Data files: the SoundFont and the MediaPipe model are loaded at runtime
# by path. Bundle them next to the exe so they ship together. The user
# can swap in a different SoundFont by replacing the file post-install.
datas = [
    ('soundfonts/GeneralUser-GS.sf2', 'soundfonts'),
    ('models/hand_landmarker.task',   'models'),
    ('config.example.yaml',           '.'),
]

# MediaPipe ships .binarypb files, calibration data, and friends that
# PyInstaller does not pick up from plain imports. collect_data_files
# walks the installed package and grabs everything non-Python.
datas += collect_data_files('mediapipe')

# FluidSynth DLLs (libfluidsynth-3, glib, sndfile, SDL3, etc.) live next
# to fluidsynth.exe. pyFluidSynth expects them at C:\tools\fluidsynth\bin
# at import time. To make the exe portable we ship the DLLs into the
# bundle root and PrePend that directory to PATH at runtime in main.py
# via a small bootstrap (see camera.py / synth.py docs).
# For now, we bundle them next to the exe; user-side install of
# FluidSynth is still required to provide the DLLs to bundle.
import os, glob
fluidsynth_bin = r'D:\FluidSynth\bin'
fluid_dlls = []
if os.path.isdir(fluidsynth_bin):
    for dll in glob.glob(os.path.join(fluidsynth_bin, '*.dll')):
        fluid_dlls.append((dll, '.'))
binaries = fluid_dlls

# OpenCV depends on a bunch of Qt and codec DLLs that collect_dynamic_libs
# picks up reliably.
binaries += collect_dynamic_libs('cv2')


a = Analysis(
    ['composair/__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # Tkinter sub-modules that PyInstaller can miss when nothing
        # in our code imports them by name.
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='composair',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,    # Keep console for now so users see logs / errors.
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='composair',
)
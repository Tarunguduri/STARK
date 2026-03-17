# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


project_root = Path.cwd()
assets_root = project_root / "assets"


def _entry_text(entry):
    return " ".join(str(part).replace("\\", "/").lower() for part in entry[:2])


def _keep_collected_data(entry):
    text = _entry_text(entry)

    if "speech_recognition/pocketsphinx-data" in text:
        return False
    if "speech_recognition/flac-linux" in text or "speech_recognition/flac-mac" in text:
        return False

    if "mediapipe/modules/" in text:
        allowed_modules = (
            "mediapipe/modules/hand_landmark/",
            "mediapipe/modules/palm_detection/",
        )
        return any(module in text for module in allowed_modules)

    return True

datas = [
    (str(project_root / "config" / "contacts.json"), "config"),
    (str(project_root / "config" / "workflows.json"), "config"),
    (str(project_root / "stark_config.yaml"), "."),
    (str(project_root / "README.md"), "."),
    (str(assets_root / "stark_icon.ico"), "assets"),
    (str(assets_root / "stark_icon.png"), "assets"),
]

hiddenimports = [
    "cv2",
    "mediapipe",
    "mediapipe.python",
    "mediapipe.python.solutions",
    "mediapipe.python.solutions.drawing_utils",
    "mediapipe.python.solutions.hands",
    "mss",
    "PIL",
    "pystray",
    "pyttsx3",
    "speech_recognition",
    "pytesseract",
    "youtubesearchpython",
    "comtypes",
    "comtypes.client",
]

datas += collect_data_files("mediapipe")
datas += collect_data_files("cv2")


a = Analysis(
    ["stark_launcher.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "tensorflow",
        "scipy",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)
a.datas = [entry for entry in a.datas if _keep_collected_data(entry)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="STARK",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(assets_root / "stark_icon.ico"),
    version=str(project_root / "stark_version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="STARK",
)

"""
STARK App Scanner — Universal 5-Layer App Discovery Engine
Pulled from STARK v2. Finds ANY installed Windows app.
"""
import os
import subprocess
import re
from pathlib import Path

HOME = Path(os.environ.get("USERPROFILE", Path.home()))

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    str(HOME / r"AppData\Local\Google\Chrome\Application\chrome.exe"),
]
SPOTIFY_PATHS = [
    str(HOME / r"AppData\Roaming\Spotify\Spotify.exe"),
    str(HOME / r"AppData\Local\Microsoft\WindowsApps\Spotify.exe"),
    r"C:\Program Files\Spotify\Spotify.exe",
    r"C:\Program Files (x86)\Spotify\Spotify.exe",
    str(HOME / r"AppData\Local\Spotify\Spotify.exe"),
]
VLC_PATHS = [
    r"C:\Program Files\VideoLAN\VLC\vlc.exe",
    r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
]

# === MS Store URI scheme table ===
STORE_URI_APPS = {
    "whatsapp": "whatsapp:", "whats app": "whatsapp:",
    "instagram": "instagram:", "facebook": "facebook:",
    "twitter": "twitter:", "x": "twitter:", "linkedin": "linkedin:",
    "tiktok": "tiktok:", "telegram": "tg:", "messenger": "ms-chat:",
    "teams": "msteams:", "microsoft teams": "msteams:",
    "onenote": "onenote:", "mail": "outlookmail:", "calendar": "outlookcal:",
    "maps": "bingmaps:", "sticky notes": "ms-stickynotes:", "xbox": "xbox:",
    "camera": "microsoft.windows.camera:", "clock": "ms-clock:",
    "spotify": "spotify:", "netflix": "netflix:",
    "disney plus": "disneyplus:", "disney+": "disneyplus:",
    "amazon prime": "primevideo:", "prime video": "primevideo:",
    "youtube": "https://www.youtube.com",
    "slack": "slack:", "zoom": "zoommtg:",
    "settings": "ms-settings:", "windows settings": "ms-settings:",
}


def find_exe(paths: list) -> str | None:
    for p in paths:
        if Path(p).exists():
            return p
    return None


def find_spotify() -> str | None:
    exe = find_exe(SPOTIFY_PATHS)
    if exe:
        return exe
    wa = HOME / r"AppData\Local\Microsoft\WindowsApps"
    if wa.exists():
        for p in wa.rglob("Spotify.exe"):
            return str(p)
    try:
        r = subprocess.run(["where", "Spotify.exe"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            line = r.stdout.strip().splitlines()[0].strip()
            if line:
                return line
    except Exception:
        pass
    return None


def _find_in_registry(app_name: str) -> str | None:
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(hive, key_path) as base:
                    for suffix in ("", ".exe"):
                        try:
                            with winreg.OpenKey(base, app_name + suffix) as key:
                                val, _ = winreg.QueryValueEx(key, "")
                                if val and Path(val).exists():
                                    return val
                        except FileNotFoundError:
                            pass
            except Exception:
                pass
    except ImportError:
        pass
    return None


def _find_in_windowsapps(name: str) -> str | None:
    wa = HOME / r"AppData\Local\Microsoft\WindowsApps"
    if wa.exists():
        nl = name.lower().replace(" ", "")
        try:
            for p in wa.rglob("*.exe"):
                if nl in p.stem.lower().replace(" ", ""):
                    return str(p)
        except Exception:
            pass
    return None


def _find_via_where(name: str) -> str | None:
    try:
        exe = name if name.endswith(".exe") else name + ".exe"
        r = subprocess.run(["where", exe], capture_output=True, text=True, timeout=3)
        if r.returncode == 0:
            line = r.stdout.strip().splitlines()[0].strip()
            if line and Path(line).exists():
                return line
    except Exception:
        pass
    return None


def smart_find_app(name: str) -> str | None:
    """Universal app finder: URI table → registry → where → WindowsApps → Start Menu lnk"""
    nl = name.lower().strip()
    # Layer 0: MS Store URI table
    for key, uri in STORE_URI_APPS.items():
        if nl == key or nl in key or key in nl:
            return uri
    # Layer 1: Registry App Paths
    reg = _find_in_registry(nl)
    if reg:
        return reg
    # Layer 2: where command
    wh = _find_via_where(nl)
    if wh:
        return wh
    # Layer 3: WindowsApps
    wa = _find_in_windowsapps(nl)
    if wa:
        return wa
    # Layer 4: Start Menu .lnk scan
    search_bases = [
        Path("C:/Users/Public/Desktop"),
        HOME / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs",
        Path("C:/ProgramData/Microsoft/Windows/Start Menu/Programs"),
    ]
    for base in search_bases:
        if not base.exists():
            continue
        try:
            for p in base.rglob("*.lnk"):
                if nl in p.stem.lower():
                    return str(p)
        except Exception:
            pass
    return None


def launch_app(path_or_uri: str, name: str = "") -> tuple[bool, str]:
    """Launch any app by path, .lnk, or URI scheme. Returns (success, message)."""
    import os
    is_uri = bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:", path_or_uri)) and \
             not path_or_uri.startswith(("C:", "D:", "E:"))
    label = name.title() if name else path_or_uri.split(":")[0].title()
    try:
        if is_uri:
            os.startfile(path_or_uri)
            return True, f"Opening {label} ✓"
        p = Path(path_or_uri)
        if p.suffix.lower() == ".lnk":
            os.startfile(str(p))
            return True, f"Opening {label} ✓"
        if p.suffix.lower() in (".exe", ".msc", ".bat", ".cmd"):
            subprocess.Popen([str(p)], shell=False)
            return True, f"Opening {label} ✓"
        os.startfile(str(p))
        return True, f"Opening {label} ✓"
    except Exception as e:
        try:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-WindowStyle", "Hidden",
                 "-Command", f"Start-Process '{path_or_uri}'"],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return True, f"Opening {label} ✓"
        except Exception:
            return False, f"Could not open {label}: {e}"


class AppScanner:
    """Builds a registry of installed apps and resolves names to paths."""

    def __init__(self):
        self.apps: dict[str, str] = {}
        self._build()

    def _build(self):
        # Windows built-ins
        builtins = {
            "notepad": "notepad.exe", "calculator": "calc.exe", "calc": "calc.exe",
            "paint": "mspaint.exe", "file explorer": "explorer.exe",
            "explorer": "explorer.exe", "task manager": "taskmgr.exe", "taskmgr": "taskmgr.exe",
            "control panel": "control.exe", "cmd": "cmd.exe",
            "command prompt": "cmd.exe", "powershell": "powershell.exe",
            "windows powershell": "powershell.exe", "settings": "ms-settings:",
            "snipping tool": "snippingtool.exe", "snip": "snippingtool.exe",
            "wordpad": "wordpad.exe", "regedit": "regedit.exe",
            "registry editor": "regedit.exe", "msconfig": "msconfig.exe",
            "device manager": "devmgmt.msc", "disk management": "diskmgmt.msc",
            "services": "services.msc", "resource monitor": "resmon.exe",
        }
        self.apps.update(builtins)

        # Apps with known paths
        known = [
            (["chrome", "google chrome", "google"], CHROME_PATHS),
            (["firefox", "mozilla firefox"], [
                r"C:\Program Files\Mozilla Firefox\firefox.exe",
                r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
            ]),
            (["edge", "microsoft edge", "msedge"], [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]),
            (["spotify"], SPOTIFY_PATHS),
            (["vlc", "vlc media player"], VLC_PATHS),
            (["word", "microsoft word", "ms word"], [
                r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
                r"C:\Program Files\Microsoft Office\root\Office17\WINWORD.EXE",
            ]),
            (["excel", "microsoft excel", "ms excel"], [
                r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
                r"C:\Program Files\Microsoft Office\root\Office17\EXCEL.EXE",
            ]),
            (["powerpoint", "ms powerpoint", "ppt"], [
                r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
            ]),
            (["teams", "microsoft teams", "ms teams"], [
                str(HOME / r"AppData\Local\Microsoft\Teams\current\Teams.exe"),
                str(HOME / r"AppData\Local\Microsoft\Teams\Teams.exe"),
            ]),
            (["discord"], [
                str(HOME / r"AppData\Roaming\Discord\Discord.exe"),
                # Keep a stable fallback path; versioned app-* folders are resolved by live search.
                str(HOME / r"AppData\Local\Discord\Discord.exe"),
            ]),
            (["telegram", "telegram desktop"], [
                str(HOME / r"AppData\Roaming\Telegram Desktop\Telegram.exe"),
                str(HOME / r"AppData\Local\Telegram Desktop\Telegram.exe"),
            ]),
            (["whatsapp", "wa"], [
                str(HOME / r"AppData\Local\WhatsApp\WhatsApp.exe"),
                str(HOME / r"AppData\Local\Programs\WhatsApp\WhatsApp.exe"),
                "whatsapp:",
            ]),
            (["zoom"], [
                str(HOME / r"AppData\Roaming\Zoom\bin\Zoom.exe"),
                r"C:\Program Files\Zoom\bin\Zoom.exe",
            ]),
            (["steam"], [
                r"C:\Program Files (x86)\Steam\steam.exe",
                r"C:\Program Files\Steam\steam.exe",
            ]),
            (["obs", "obs studio"], [
                r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
            ]),
            (["notepad++", "notepad plus", "npp"], [
                r"C:\Program Files\Notepad++\notepad++.exe",
                r"C:\Program Files (x86)\Notepad++\notepad++.exe",
            ]),
            (["7zip", "7-zip", "7 zip"], [
                r"C:\Program Files\7-Zip\7zFM.exe",
                r"C:\Program Files (x86)\7-Zip\7zFM.exe",
            ]),
            (["brave", "brave browser"], [
                str(HOME / r"AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe"),
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            ]),
            (["opera"], [
                str(HOME / r"AppData\Local\Programs\Opera\opera.exe"),
            ]),
            (["postman"], [
                str(HOME / r"AppData\Local\Postman\Postman.exe"),
            ]),
            (["figma"], [
                str(HOME / r"AppData\Local\Figma\Figma.exe"),
            ]),
            (["android studio"], [
                r"C:\Program Files\Android\Android Studio\bin\studio64.exe",
            ]),
            (["blender"], [
                r"C:\Program Files\Blender Foundation\Blender\blender.exe",
                r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
            ]),
            (["gimp"], [
                r"C:\Program Files\GIMP 2\bin\gimp-2.10.exe",
                r"C:\Program Files\GIMP 3\bin\gimp-3.0.exe",
            ]),
            (["winrar"], [
                r"C:\Program Files\WinRAR\WinRAR.exe",
                r"C:\Program Files (x86)\WinRAR\WinRAR.exe",
            ]),
        ]

        for aliases, paths in known:
            exe = find_exe(paths)
            if not exe:
                exe = smart_find_app(aliases[0])
            if exe:
                for alias in aliases:
                    self.apps[alias] = exe

        # VS Code (special path)
        vsc_paths = [
            HOME / "AppData/Local/Programs/Microsoft VS Code/Code.exe",
            HOME / "AppData/Local/Programs/Microsoft VS Code/bin/code.cmd",
            Path(r"C:\Program Files\Microsoft VS Code\Code.exe"),
            Path(r"C:\Program Files\Microsoft VS Code\bin\code.cmd"),
        ]
        for vsc in vsc_paths:
            if vsc.exists():
                p_str = str(vsc)
                for k in ["vs code", "vscode", "visual studio code", "code"]:
                    self.apps[k] = p_str
                break

        # Scan Start Menu + Desktop .lnk shortcuts
        scan_bases = [
            HOME / "Desktop",
            Path("C:/Users/Public/Desktop"),
            HOME / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs",
            Path("C:/ProgramData/Microsoft/Windows/Start Menu/Programs"),
        ]
        skip = ("uninstall", "setup", "installer", "update", "repair", "remove", "readme")
        for base in scan_bases:
            if not base.exists():
                continue
            for pat in ("**/*.lnk", "**/*.url"):
                try:
                    for p in base.glob(pat):
                        n = p.stem.lower().strip()
                        if n and not any(x in n for x in skip) and n not in self.apps:
                            self.apps[n] = str(p)
                except Exception:
                    pass

    def find(self, name: str) -> str | None:
        n = name.lower().strip()
        # Exact
        if n in self.apps:
            return self.apps[n]
        # Prefix / suffix
        for k, v in self.apps.items():
            if k.startswith(n) or n.startswith(k):
                return v
        # Substring
        for k, v in self.apps.items():
            if n in k or k in n:
                return v
        # Universal live search
        found = smart_find_app(n)
        if found:
            self.apps[n] = found
            return found
        return None

    def list_all(self) -> list:
        return sorted(self.apps.keys())

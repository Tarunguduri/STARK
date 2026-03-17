import os
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote, quote_plus


try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False

try:
    import pyautogui

    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    pyautogui = None
    HAS_PYAUTOGUI = False


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)


def _open_in_browser(url: str) -> None:
    try:
        from core.app_scanner import AppScanner

        scanner = AppScanner()
        brave_path = scanner.find("brave")
        if brave_path and not brave_path.startswith(("http", "spotify:", "whatsapp:")):
            subprocess.Popen([brave_path, url])
            return
    except Exception:
        pass
    webbrowser.open(url)


def _find_spotify_exe() -> str | None:
    from core.app_scanner import find_spotify

    return find_spotify()


def _spotify_is_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Spotify.exe", "/NH"],
            capture_output=True,
            text=True,
            timeout=4,
        )
        return "Spotify.exe" in result.stdout
    except Exception:
        return False


def _spotify_track_id(query: str) -> str | None:
    if not HAS_REQUESTS:
        return None

    try:
        token_response = requests.get(
            "https://open.spotify.com/get_access_token?reason=transport&productType=web_player",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5,
        )
        token = token_response.json().get("accessToken", "")
        if not token:
            return None

        search_response = requests.get(
            "https://api.spotify.com/v1/search",
            params={"q": query, "type": "track", "limit": 1},
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        items = search_response.json().get("tracks", {}).get("items", [])
        if items:
            return items[0]["id"]
    except Exception:
        pass

    return None


_SPOTIFY_SEARCH_SCRIPT = r"""
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class SpotifyControl {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    [StructLayout(LayoutKind.Sequential)]
    public struct INPUT {
        public uint type;
        public KEYBDINPUT ki;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 8)] public byte[] pad;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KEYBDINPUT {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }

    public static void KeyTap(ushort vk) {
        var down = new INPUT { type = 1, ki = new KEYBDINPUT { wVk = vk }, pad = new byte[8] };
        var up = new INPUT { type = 1, ki = new KEYBDINPUT { wVk = vk, dwFlags = 2 }, pad = new byte[8] };
        int size = Marshal.SizeOf(typeof(INPUT));
        SendInput(1, new INPUT[] { down }, size);
        System.Threading.Thread.Sleep(120);
        SendInput(1, new INPUT[] { up }, size);
    }
}
"@
Add-Type -AssemblyName System.Windows.Forms
$query = @'
__QUERY__
'@
$spotify = $null
for ($i = 0; $i -lt 20; $i++) {
    $spotify = Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne "" } | Select-Object -First 1
    if ($spotify) { break }
    Start-Sleep -Milliseconds 600
}
if (-not $spotify) { exit 1 }
[SpotifyControl]::ShowWindow([IntPtr]$spotify.MainWindowHandle, 3) | Out-Null
[SpotifyControl]::SetForegroundWindow([IntPtr]$spotify.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 1500
[System.Windows.Forms.Clipboard]::SetText($query)
[System.Windows.Forms.SendKeys]::SendWait("^l")
Start-Sleep -Milliseconds 250
[System.Windows.Forms.SendKeys]::SendWait("^a")
Start-Sleep -Milliseconds 150
[System.Windows.Forms.SendKeys]::SendWait("^v")
Start-Sleep -Milliseconds 250
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Milliseconds 1200
[SpotifyControl]::KeyTap(0x28)
Start-Sleep -Milliseconds 250
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
Start-Sleep -Milliseconds 600
[System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
"""


def _focus_and_play_spotify(query: str) -> None:
    script = _SPOTIFY_SEARCH_SCRIPT.replace("__QUERY__", query)
    try:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        if HAS_PYAUTOGUI:
            try:
                time.sleep(1.5)
                pyautogui.hotkey("ctrl", "l")
                time.sleep(0.2)
                pyautogui.hotkey("ctrl", "a")
                pyautogui.write(query, interval=0.03)
                pyautogui.press("enter")
                time.sleep(1.0)
                pyautogui.press("down")
                pyautogui.press("enter")
                time.sleep(0.4)
                pyautogui.press("enter")
            except Exception:
                pass


def play_spotify(query: str) -> tuple[bool, str]:
    query = query.strip()
    if not query:
        return False, "A Spotify query is required."

    exe = _find_spotify_exe()
    track_id = _spotify_track_id(query)
    search_uri = f"spotify:search:{quote(query)}"
    web_url = (
        f"https://open.spotify.com/track/{track_id}"
        if track_id
        else f"https://open.spotify.com/search/{quote(query)}"
    )

    def _worker() -> None:
        already_running = _spotify_is_running()
        try:
            os.startfile(search_uri)
        except Exception:
            if exe:
                try:
                    subprocess.Popen([exe, search_uri], creationflags=CREATE_NEW_CONSOLE)
                except Exception:
                    pass
        time.sleep(5.0 if not already_running else 3.0)
        _focus_and_play_spotify(query)

    if exe:
        threading.Thread(target=_worker, daemon=True).start()
        return True, f"Playing '{query}' on Spotify."

    try:
        os.startfile(search_uri)
        return True, f"Opened Spotify search for '{query}'."
    except Exception:
        _open_in_browser(web_url)
        return True, f"Opened Spotify Web for '{query}'."


def play_youtube(query: str) -> tuple[bool, str]:
    query = query.strip()
    if not query:
        return False, "A YouTube query is required."

    try:
        from youtubesearchpython import VideosSearch

        result = VideosSearch(query, limit=1).result()
        videos = result.get("result") or []
        if videos:
            video_url = videos[0]["link"]
            separator = "&" if "?" in video_url else "?"
            _open_in_browser(f"{video_url}{separator}autoplay=1")
            return True, f"Playing '{query}' on YouTube."
    except Exception:
        pass

    _open_in_browser(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
    return True, f"Opened YouTube search for '{query}'."


def play_netflix(query: str) -> tuple[bool, str]:
    query = query.strip()
    if query:
        _open_in_browser(f"https://www.netflix.com/search?q={quote_plus(query)}")
        return True, f"Opened Netflix search for '{query}'."
    _open_in_browser("https://www.netflix.com")
    return True, "Opened Netflix."


def play_media(platform: str, query: str) -> tuple[bool, str]:
    platform_name = (platform or "").strip().lower()

    if platform_name == "spotify":
        return play_spotify(query)
    if platform_name == "youtube":
        return play_youtube(query)
    if platform_name == "netflix":
        return play_netflix(query)
    return play_youtube(query)

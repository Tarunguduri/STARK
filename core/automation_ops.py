import builtins
import os
import subprocess
import time
import webbrowser
from typing import Any, Dict
from urllib.parse import quote_plus

from core.app_scanner import AppScanner, launch_app as scanner_launch
from core.ghost_controller import GhostController
from core.media_play import play_media
from core.reasoning import bind_workflow_to_gesture, list_gesture_workflows, reset_workflow, update_workflow
from core.whatsapp_message import add_or_update_contact, list_contacts, remove_contact, send_whatsapp_message


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

try:
    import pyautogui

    HAS_PYAUTOGUI = True
except ImportError:
    pyautogui = None
    HAS_PYAUTOGUI = False


def execute_automation_action(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    ghost = GhostController()
    params = params or {}

    try:
        if action in {"launch_app", "open_app"}:
            return _launch_app(
                params.get("app_name") or params.get("value", ""),
                target_path=params.get("path") or params.get("target") or params.get("workspace"),
            )

        if action == "type_text":
            text = params.get("text", "")
            success = ghost.type_text(text)
            return {"success": success, "message": f"Typed text: {text[:20]}..."}

        if action == "click_mouse":
            x = params.get("x", 0)
            y = params.get("y", 0)
            button = params.get("button", "left")
            success = ghost.click_mouse(x, y, button)
            return {"success": success, "message": f"Clicked {button} at ({x}, {y})"}

        if action == "press_key":
            key = params.get("key", "")
            success = ghost.press_key(key)
            return {"success": success, "message": f"Pressed key: {key}"}

        if action == "run_terminal":
            command = params.get("command", "")
            success = ghost.run_command(command)
            return {"success": success, "message": f"Ran command: {command}"}

        if action == "delay":
            seconds = float(params.get("seconds", 1))
            time.sleep(seconds)
            return {"success": True, "message": f"Delayed for {seconds}s"}

        if action == "open_url":
            url = params.get("url", "")
            webbrowser.open(url)
            return {"success": True, "message": f"Opened URL: {url}"}

        if action == "play_media":
            platform = params.get("platform", "")
            query = params.get("query", params.get("value", ""))
            success, message = play_media(platform, query)
            return {"success": success, "message": message}

        if action == "send_whatsapp_message":
            return send_whatsapp_message(
                params.get("contact", params.get("value", "")),
                params.get("message", ""),
            )

        if action in {"add_contact", "update_contact"}:
            return add_or_update_contact(params.get("name", params.get("value", "")), params.get("phone", ""))

        if action == "remove_contact":
            return remove_contact(params.get("name", params.get("value", "")))

        if action == "list_contacts":
            return list_contacts()

        if action == "search_web":
            query = params.get("query", "")
            webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
            return {"success": True, "message": f"Searching Google for: {query}"}

        if action == "close_apps":
            apps = params.get("value", params.get("apps", []))
            if isinstance(apps, str):
                apps = [apps]
            closed = []
            for app in apps:
                exe = app if str(app).lower().endswith(".exe") else f"{app}.exe"
                try:
                    subprocess.run(["taskkill", "/F", "/IM", exe], capture_output=True, timeout=5)
                    closed.append(app)
                except Exception:
                    pass
            return {"success": True, "message": f"Closed: {', '.join(closed) or 'none'}"}

        if action == "set_volume":
            level = int(params.get("value", params.get("level", 50)))
            level = max(0, min(100, level))
            if HAS_PYAUTOGUI:
                current = 50
                if level == 0:
                    for _ in range(50):
                        pyautogui.press("volumedown")
                else:
                    for _ in range(50):
                        pyautogui.press("volumedown")
                    steps = max(0, min(50, round(level / 2)))
                    for _ in range(steps):
                        pyautogui.press("volumeup")
                return {"success": True, "message": f"Volume adjusted to about {level}%"}
            return {"success": False, "message": "pyautogui is required to set volume."}

        if action == "activate_listening":
            setattr(builtins, "_stark_activate_mic", True)
            return {"success": True, "message": "STARK is listening."}

        if action == "create_folder":
            folder = params.get("value", params.get("path", "ai_project"))
            if not os.path.isabs(folder):
                folder = os.path.join(os.getcwd(), folder)
            absolute_path = os.path.abspath(folder)
            already_exists = os.path.isdir(absolute_path)
            os.makedirs(absolute_path, exist_ok=True)
            if already_exists:
                return {"success": True, "message": f"Folder already exists: {absolute_path}"}
            return {"success": True, "message": f"Folder created at: {absolute_path}"}

        if action == "open_terminal":
            try:
                subprocess.Popen(["wt"], creationflags=CREATE_NEW_CONSOLE)
            except FileNotFoundError:
                subprocess.Popen("start cmd", shell=True)
            return {"success": True, "message": "Terminal opened"}

        if action == "update_workflow":
            return update_workflow(params.get("gesture", ""), params.get("actions", []))

        if action == "bind_workflow":
            return bind_workflow_to_gesture(params.get("gesture", ""), params.get("workflow", ""))

        if action == "list_workflows":
            return list_gesture_workflows()

        if action == "reset_workflow":
            return reset_workflow(params.get("gesture", params.get("value", "")))

        return {"success": False, "message": f"Unknown automation action: {action}"}
    except Exception as exc:
        return {"success": False, "message": f"Automation error: {exc}"}


def _launch_app(app_name: str, target_path: str | None = None) -> Dict[str, Any]:
    app_name = (app_name or "").strip()
    if not app_name:
        return {"success": False, "message": "App name is required."}

    app_name_lower = app_name.lower()

    if app_name_lower in {"vscode", "vs code", "visual studio code", "code"}:
        return _launch_vscode(target_path)

    scanner = AppScanner()
    app_path = scanner.find(app_name)
    if app_path:
        if app_path.lower().endswith((".cmd", ".bat")):
            subprocess.Popen(app_path, shell=True)
            return {"success": True, "message": f"Launched {app_name} (shell)"}
        success, message = scanner_launch(app_path, app_name)
        return {"success": success, "message": message}

    ghost = GhostController()
    success = ghost.open_application(app_name)
    return {"success": success, "message": f"{'Opened' if success else 'Could not find'}: {app_name}"}


def _launch_vscode(target_path: str | None = None) -> Dict[str, Any]:
    workspace_path = os.path.abspath(target_path) if target_path else os.getcwd()

    if target_path and not os.path.exists(workspace_path):
        try:
            os.makedirs(workspace_path, exist_ok=True)
        except Exception:
            workspace_path = os.getcwd()

    cli_candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "bin", "code.cmd"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "bin", "code"),
        "code",
    ]
    exe_candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
    ]

    cli_args = ["--new-window", workspace_path]

    for candidate in cli_candidates:
        if candidate != "code" and not os.path.exists(candidate):
            continue
        try:
            if candidate.lower().endswith(".cmd"):
                subprocess.Popen(
                    ["cmd", "/c", candidate, *cli_args],
                    creationflags=CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen([candidate, *cli_args], creationflags=CREATE_NEW_CONSOLE)
            _focus_window_title("Visual Studio Code")
            return {"success": True, "message": f"Opened VS Code workspace: {workspace_path}"}
        except Exception:
            continue

    for candidate in exe_candidates:
        if os.path.exists(candidate):
            try:
                subprocess.Popen([candidate, workspace_path])
                _focus_window_title("Visual Studio Code")
                return {"success": True, "message": f"Opened VS Code at: {workspace_path}"}
            except Exception:
                continue

    return {"success": False, "message": "VS Code was not found on this system."}


def _focus_window_title(window_title: str) -> None:
    try:
        ps_script = (
            '$ws = New-Object -ComObject WScript.Shell; '
            f'Start-Sleep -Milliseconds 700; '
            f'$null = $ws.AppActivate("{window_title}")'
        )
        subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps_script],
            creationflags=CREATE_NO_WINDOW,
        )
    except Exception:
        pass

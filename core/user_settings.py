import json
import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional


APP_NAME = "STARK"


def _is_directory_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_path = path / ".write_test"
        with open(probe_path, "w", encoding="utf-8") as handle:
            handle.write("ok")
        probe_path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


@lru_cache(maxsize=1)
def get_user_data_dir() -> Path:
    override = os.environ.get("STARK_SETTINGS_DIR", "").strip()
    if override:
        override_path = Path(override).expanduser()
        if _is_directory_writable(override_path):
            return override_path

    candidates = []
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        candidates.append(Path(base) / APP_NAME)
        local_base = os.environ.get("LOCALAPPDATA", "").strip()
        if local_base:
            candidates.append(Path(local_base) / APP_NAME)
    else:
        candidates.append(Path.home() / f".{APP_NAME.lower()}")

    candidates.append(get_bundle_root() / ".stark_user_data")

    for candidate in candidates:
        if _is_directory_writable(candidate):
            return candidate

    # Fall back to the first candidate even if the probe failed so callers get a stable path.
    return candidates[0]


def get_settings_path() -> Path:
    return get_user_data_dir() / "settings.json"


def get_bundle_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def ensure_user_file(filename: str, bundled_relative_path: str) -> Path:
    target_path = get_user_data_dir() / filename
    if target_path.exists():
        return target_path

    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_path = get_bundle_root() / bundled_relative_path
    if source_path.exists():
        try:
            shutil.copy2(source_path, target_path)
        except Exception:
            target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        target_path.touch()
    return target_path


def get_contacts_path() -> Path:
    return ensure_user_file("contacts.json", os.path.join("config", "contacts.json"))


def get_workflows_path() -> Path:
    return ensure_user_file("workflows.json", os.path.join("config", "workflows.json"))


def get_runtime_config_path() -> Path:
    return ensure_user_file("stark_config.yaml", "stark_config.yaml")


def load_user_settings() -> Dict[str, Any]:
    path = get_settings_path()
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            content = handle.read().strip()
        if not content:
            return {}
        data = json.loads(content)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_user_settings(settings: Dict[str, Any]) -> Path:
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=4)
    return path


def get_saved_api_key() -> str:
    settings = load_user_settings()
    return str(settings.get("groq_api_key", "") or "").strip()


def save_api_key(api_key: str) -> Path:
    settings = load_user_settings()
    settings["groq_api_key"] = (api_key or "").strip()
    return save_user_settings(settings)


def clear_api_key() -> Optional[Path]:
    settings = load_user_settings()
    if "groq_api_key" not in settings:
        return None
    settings.pop("groq_api_key", None)
    return save_user_settings(settings)


def load_api_key_into_env(prefer_saved: bool = True) -> str:
    existing_env = os.environ.get("GROQ_API_KEY", "").strip()
    saved_key = get_saved_api_key()

    if prefer_saved and saved_key:
        os.environ["GROQ_API_KEY"] = saved_key
        return saved_key

    if existing_env:
        return existing_env

    if saved_key:
        os.environ["GROQ_API_KEY"] = saved_key
        return saved_key

    return ""


def ensure_api_key(
    gui: bool = False,
    force_prompt: bool = False,
    parent=None,
    allow_skip: bool = True,
) -> str:
    current_key = load_api_key_into_env(prefer_saved=True)
    if current_key and not force_prompt:
        return current_key

    prompt_fn = _prompt_for_api_key_gui if gui else _prompt_for_api_key_cli
    entered_key = prompt_fn(parent=parent, allow_skip=allow_skip)
    if entered_key:
        save_api_key(entered_key)
        os.environ["GROQ_API_KEY"] = entered_key
        return entered_key
    return ""


def mask_api_key(api_key: str) -> str:
    value = (api_key or "").strip()
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _prompt_for_api_key_cli(parent=None, allow_skip: bool = True) -> str:
    prompt = "Enter your Groq API key"
    if allow_skip:
        prompt += " (leave blank to continue without AI)"
    prompt += ": "

    try:
        import getpass

        entered = getpass.getpass(prompt)
    except Exception:
        entered = input(prompt)

    return (entered or "").strip()


def _prompt_for_api_key_gui(parent=None, allow_skip: bool = True) -> str:
    try:
        import tkinter as tk
        from tkinter import messagebox, simpledialog
    except Exception:
        return _prompt_for_api_key_cli(allow_skip=allow_skip)

    created_root = False
    root = parent
    if root is None:
        root = tk.Tk()
        root.withdraw()
        created_root = True

    try:
        message = "Enter your Groq API key to unlock AI features."
        if allow_skip:
            message += "\nYou can leave this blank and continue in limited mode."

        entered = simpledialog.askstring(
            "STARK API Key Setup",
            message,
            parent=root,
            show="*",
        )

        if entered and entered.strip():
            path = save_api_key(entered.strip())
            os.environ["GROQ_API_KEY"] = entered.strip()
            messagebox.showinfo(
                "STARK Setup",
                f"API key saved to:\n{path}",
                parent=root,
            )
            return entered.strip()

        if not allow_skip:
            messagebox.showwarning(
                "STARK Setup",
                "An API key is required to continue.",
                parent=root,
            )
        return ""
    finally:
        if created_root:
            root.destroy()

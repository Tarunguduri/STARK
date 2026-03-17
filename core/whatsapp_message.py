import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

from core.user_settings import get_contacts_path


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTACTS_PATH = get_contacts_path()

try:
    import pyautogui

    pyautogui.FAILSAFE = False
    HAS_PYAUTOGUI = True
except ImportError:
    pyautogui = None
    HAS_PYAUTOGUI = False


def _clean_contact_key(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _display_contact_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def load_contacts_raw(path: Path = CONTACTS_PATH) -> Dict[str, str]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read().strip()
    if not content:
        return {}
    data = json.loads(content)
    return {_display_contact_name(str(key)): str(value).strip() for key, value in data.items()}


def load_contacts(path: Path = CONTACTS_PATH) -> Dict[str, str]:
    data = load_contacts_raw(path)
    return {_clean_contact_key(str(key)): str(value).strip() for key, value in data.items()}


def save_contacts_raw(contacts: Dict[str, str], path: Path = CONTACTS_PATH) -> None:
    ordered = {
        _display_contact_name(name): str(phone).strip()
        for name, phone in sorted(contacts.items(), key=lambda item: _clean_contact_key(item[0]))
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(ordered, handle, indent=4)


def _find_display_contact_key(name: str, contacts: Optional[Dict[str, str]] = None) -> Optional[str]:
    contacts = contacts if contacts is not None else load_contacts_raw()
    normalized_name = _clean_contact_key(name)
    for display_name in contacts:
        current = _clean_contact_key(display_name)
        if normalized_name == current or normalized_name in current or current in normalized_name:
            return display_name
    return None


def list_contacts() -> Dict[str, Any]:
    contacts = load_contacts_raw()
    if not contacts:
        return {"success": True, "message": "No contacts saved yet.", "contacts": {}}

    lines = ["Saved contacts:"]
    for name, phone in sorted(contacts.items(), key=lambda item: _clean_contact_key(item[0])):
        lines.append(f"- {name}: {phone}")
    return {"success": True, "message": "\n".join(lines), "contacts": contacts}


def add_or_update_contact(name: str, phone: str) -> Dict[str, Any]:
    display_name = _display_contact_name(name)
    normalized_phone = _normalize_phone_number(phone)
    if not display_name or not normalized_phone:
        return {"success": False, "message": "A contact name and phone number are required."}

    contacts = load_contacts_raw()
    existing_key = _find_display_contact_key(display_name, contacts)
    target_key = existing_key or display_name
    action_label = "Updated" if existing_key else "Added"
    contacts[target_key] = normalized_phone
    save_contacts_raw(contacts)
    return {
        "success": True,
        "message": f"{action_label} contact '{target_key}' with phone {normalized_phone}.",
        "contact": target_key,
        "phone": normalized_phone,
    }


def remove_contact(name: str) -> Dict[str, Any]:
    display_name = _display_contact_name(name)
    contacts = load_contacts_raw()
    existing_key = _find_display_contact_key(display_name, contacts)
    if not existing_key:
        return {"success": False, "message": f"Contact '{display_name}' was not found."}

    contacts.pop(existing_key, None)
    save_contacts_raw(contacts)
    return {"success": True, "message": f"Removed contact '{existing_key}'."}


def parse_message_command(command_text: str, contacts: Optional[Dict[str, str]] = None) -> Optional[Dict[str, str]]:
    match = re.match(
        r"^(?:message|text|send whatsapp(?: message)? to)\s+(.+)$",
        (command_text or "").strip(),
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    remainder = match.group(1).strip()
    contacts = contacts if contacts is not None else load_contacts()

    quoted_match = re.match(r"^[\"']([^\"']+)[\"']\s+(.+)$", remainder)
    if quoted_match:
        return {
            "contact": quoted_match.group(1).strip(),
            "message": quoted_match.group(2).strip(),
        }

    for contact_name in sorted(contacts.keys(), key=len, reverse=True):
        contact_pattern = r"^" + r"\s+".join(re.escape(part) for part in contact_name.split())
        contact_match = re.match(
            contact_pattern + r"(?:\s+|[,:-]\s*)(.+)$",
            remainder,
            flags=re.IGNORECASE,
        )
        if contact_match:
            return {
                "contact": contact_name,
                "message": contact_match.group(1).strip(),
            }

    phone_match = re.match(r"^([+0-9][0-9 ()-]{7,})\s+(.+)$", remainder)
    if phone_match:
        return {
            "contact": phone_match.group(1).strip(),
            "message": phone_match.group(2).strip(),
        }

    parts = remainder.split(None, 1)
    if len(parts) == 2:
        return {
            "contact": parts[0].strip(),
            "message": parts[1].strip(),
        }

    return None


def resolve_contact(contact: str, contacts: Optional[Dict[str, str]] = None) -> Optional[str]:
    if not contact:
        return None

    clean_contact = contact.strip()
    clean_key = _clean_contact_key(clean_contact)
    contacts = contacts if contacts is not None else load_contacts()

    if clean_key in contacts:
        return _normalize_phone_number(contacts[clean_key])

    if re.fullmatch(r"[+0-9][0-9 ()-]{7,}", clean_contact):
        return _normalize_phone_number(clean_contact)

    for name, number in contacts.items():
        if clean_key == name or clean_key in name:
            return _normalize_phone_number(number)

    return None


def send_whatsapp_message(contact: str, message: str, wait_seconds: float = 3.0) -> Dict[str, Any]:
    if not contact or not message:
        return {"success": False, "message": "Both contact and message are required."}

    phone = resolve_contact(contact)

    try:
        logger.info("[Action] send_whatsapp_message(contact=%s)", contact)

        if phone:
            result = _send_to_phone_in_desktop_app(phone, message, wait_seconds=wait_seconds)
            if result.get("success"):
                return result

        if not HAS_PYAUTOGUI:
            if phone:
                return {
                    "success": False,
                    "message": "pyautogui is required to confirm the WhatsApp desktop message send.",
                }
            return {
                "success": False,
                "message": f"Contact '{contact}' was not found in your saved contacts and pyautogui is required to search in the WhatsApp app.",
            }

        result = _search_and_send_in_desktop_app(contact, message, wait_seconds=wait_seconds)
        if result.get("success"):
            return result

        if phone:
            return {
                "success": False,
                "message": (
                    "WhatsApp desktop opened, but STARK could not confirm the message send. "
                    "Please check if the chat opened in the app."
                ),
            }
        return {
            "success": False,
            "message": (
                f"Could not find '{contact}' in your saved contacts or in the WhatsApp desktop search. "
                "Use quotes for multi-word names or save the contact through the chatbot."
            ),
        }
    except Exception as exc:
        return {"success": False, "message": f"Failed to send WhatsApp message: {exc}"}


def _normalize_phone_number(raw_phone: str) -> str:
    digits = re.sub(r"\D", "", raw_phone or "")
    return digits


def _launch_whatsapp_app() -> bool:
    try:
        from core.app_scanner import AppScanner, launch_app

        scanner = AppScanner()
        app_path = scanner.find("whatsapp")
        if not app_path:
            return False
        success, _ = launch_app(app_path, "whatsapp")
        return success
    except Exception:
        try:
            os.startfile("whatsapp:")
            return True
        except Exception:
            return False


def _send_to_phone_in_desktop_app(phone: str, message: str, wait_seconds: float = 3.0) -> Dict[str, Any]:
    encoded_message = quote(message)
    desktop_uri = f"whatsapp://send?phone={phone}&text={encoded_message}"

    try:
        os.startfile(desktop_uri)
    except Exception:
        launched = _launch_whatsapp_app()
        if not launched:
            return {"success": False, "message": "WhatsApp desktop app could not be launched."}
        time.sleep(wait_seconds)
        return _search_and_send_in_desktop_app(phone, message, wait_seconds=1.0)

    time.sleep(wait_seconds)
    if HAS_PYAUTOGUI:
        pyautogui.press("enter")
        return {"success": True, "message": f"WhatsApp desktop message sent to {phone}."}

    return {
        "success": False,
        "message": "WhatsApp desktop opened, but pyautogui is unavailable to press Enter.",
    }


def _search_and_send_in_desktop_app(contact: str, message: str, wait_seconds: float = 3.0) -> Dict[str, Any]:
    if not _launch_whatsapp_app():
        return {"success": False, "message": "WhatsApp desktop app could not be launched."}

    time.sleep(wait_seconds)

    if not HAS_PYAUTOGUI:
        return {"success": False, "message": "pyautogui is required for WhatsApp desktop search automation."}

    try:
        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.4)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.write(contact, interval=0.03)
        time.sleep(1.2)
        pyautogui.press("down")
        time.sleep(0.2)
        pyautogui.press("enter")
        time.sleep(0.8)
        pyautogui.write(message, interval=0.02)
        time.sleep(0.2)
        pyautogui.press("enter")
        return {"success": True, "message": f"WhatsApp desktop message sent to {contact}."}
    except Exception as exc:
        return {"success": False, "message": f"WhatsApp desktop automation failed: {exc}"}

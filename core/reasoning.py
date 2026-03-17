import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from core.user_settings import get_workflows_path
from core.whatsapp_message import parse_message_command


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_PATH = get_workflows_path()

GESTURE_ALIASES = {
    "open palm": "Open Palm",
    "open_palm": "Open Palm",
    "palm": "Open Palm",
    "peace": "Peace Sign",
    "peace sign": "Peace Sign",
    "peace_sign": "Peace Sign",
    "rock": "Rock Sign",
    "rock sign": "Rock Sign",
    "rock_sign": "Rock Sign",
    "fist": "Fist",
    "point": "Pointing",
    "pointing": "Pointing",
    "single finger": "Single Finger",
    "single_finger": "Single Finger",
    "one finger": "Single Finger",
    "ok": "OK Sign",
    "ok sign": "OK Sign",
    "ok_sign": "OK Sign",
}

GESTURE_PATTERN_TEXT = "|".join(
    sorted((re.escape(alias) for alias in GESTURE_ALIASES.keys()), key=len, reverse=True)
)

WORKFLOW_TEMPLATES = {
    "coding_workspace": [
        {"action": "launch_app", "params": {"app_name": "vscode"}},
        {"action": "open_terminal", "params": {}},
        {"action": "play_media", "params": {"platform": "youtube", "query": "coding music"}},
    ],
    "research_mode": [
        {"action": "launch_app", "params": {"app_name": "brave"}},
        {"action": "open_url", "params": {"url": "https://arxiv.org"}},
        {"action": "play_media", "params": {"platform": "youtube", "query": "latest ai research"}},
    ],
    "entertainment_mode": [
        {"action": "play_media", "params": {"platform": "youtube", "query": "party playlist"}},
        {"action": "set_volume", "params": {"value": 70}},
    ],
    "focus_mode": [
        {"action": "close_apps", "params": {"value": ["chrome", "spotify"]}},
        {"action": "press_key", "params": {"key": "win+d"}},
        {"action": "set_volume", "params": {"value": 0}},
    ],
}

DEFAULT_GESTURE_WORKFLOWS = {
    "Open Palm": [
        {"action": "create_folder", "params": {"value": "ai_project"}},
        {"action": "launch_app", "params": {"app_name": "vscode", "path": "ai_project"}},
        {"action": "delay", "params": {"seconds": 3.0}},
        {"action": "open_terminal", "params": {}},
        {"action": "play_media", "params": {"platform": "youtube", "query": "lofi music"}},
    ],
    "Peace Sign": [
        {"action": "run_terminal", "params": {"command": "start brave"}},
        {"action": "delay", "params": {"seconds": 2.0}},
        {"action": "play_media", "params": {"platform": "youtube", "query": "latest ai research news 2026"}},
        {"action": "open_url", "params": {"url": "https://arxiv.org"}},
    ],
    "Rock Sign": [
        {"action": "play_media", "params": {"platform": "youtube", "query": "the weeknd playlist"}},
        {"action": "set_volume", "params": {"value": 70}},
    ],
    "Fist": [
        {"action": "close_apps", "params": {"value": ["chrome", "spotify"]}},
        {"action": "press_key", "params": {"key": "win+d"}},
        {"action": "set_volume", "params": {"value": 0}},
    ],
    "Pointing": [
        {"action": "run_terminal", "params": {"command": "start brave"}},
    ],
    "Single Finger": [
        {"action": "activate_listening", "params": {}},
    ],
    "OK Sign": [
        {"action": "search_web", "params": {"query": "STARK project documentation"}},
    ],
}


def normalize_gesture_name(name: str) -> str:
    if not name:
        return ""
    compact = name.strip().lower().replace("-", " ").replace("_", " ")
    compact = re.sub(r"\s+", " ", compact)
    return GESTURE_ALIASES.get(compact, compact.title())


def workflow_key_for_gesture(name: str) -> str:
    canonical = normalize_gesture_name(name)
    return canonical.lower().replace(" ", "_")


def normalize_action_step(step: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(step, dict):
        raise ValueError("Workflow step must be a dictionary")

    action = str(step.get("action", "")).strip()
    if not action:
        raise ValueError("Workflow step is missing 'action'")

    params = dict(step.get("params") or {})
    for key, value in step.items():
        if key not in {"action", "params"}:
            params.setdefault(key, value)

    if action in {"launch_app", "open_app"}:
        params.setdefault("app_name", params.pop("value", params.get("app_name", "")))
    elif action == "play_media":
        params.setdefault("platform", params.get("platform", "youtube"))
        params.setdefault("query", params.pop("value", params.get("query", "")))
    elif action == "open_url":
        params.setdefault("url", params.pop("value", params.get("url", "")))
    elif action == "search_web":
        params.setdefault("query", params.pop("value", params.get("query", "")))
    elif action == "create_folder":
        params.setdefault("value", params.get("path", params.get("value", "")))
    elif action == "press_key":
        params.setdefault("key", params.pop("value", params.get("key", "")))
    elif action == "send_whatsapp_message":
        params.setdefault("contact", params.pop("value", params.get("contact", "")))
        params.setdefault("message", params.get("message", ""))
    elif action in {"add_contact", "update_contact"}:
        params.setdefault("name", params.pop("value", params.get("name", "")))
        params.setdefault("phone", params.get("phone", ""))
    elif action == "remove_contact":
        params.setdefault("name", params.pop("value", params.get("name", "")))
    elif action == "reset_workflow":
        params.setdefault("gesture", params.pop("value", params.get("gesture", "")))

    return {"action": action, "params": params}


def normalize_workflow_steps(steps: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for step in steps or []:
        normalized.append(normalize_action_step(step))
    return normalized


def load_workflows(path: Path = WORKFLOWS_PATH) -> Dict[str, List[Dict[str, Any]]]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        content = handle.read().strip()
    if not content:
        return {}
    data = json.loads(content)
    return {normalize_gesture_name(key): normalize_workflow_steps(value) for key, value in data.items()}


def save_workflows(workflows: Dict[str, List[Dict[str, Any]]], path: Path = WORKFLOWS_PATH) -> None:
    ordered = {normalize_gesture_name(key): normalize_workflow_steps(value) for key, value in workflows.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(ordered, handle, indent=4)


def update_workflow(gesture: str, actions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    if not gesture:
        return {"success": False, "message": "Gesture name is required."}

    normalized_gesture = normalize_gesture_name(gesture)
    try:
        normalized_actions = normalize_workflow_steps(actions)
    except Exception as exc:
        return {"success": False, "message": f"Invalid workflow actions: {exc}"}

    workflows = load_workflows()
    workflows[normalized_gesture] = normalized_actions
    save_workflows(workflows)
    logger.info("[System] Updated workflow for %s", normalized_gesture)
    return {
        "success": True,
        "message": f"Workflow updated for {normalized_gesture}.",
        "gesture": normalized_gesture,
        "actions": normalized_actions,
    }


def bind_workflow_to_gesture(gesture: str, workflow_name: str) -> Dict[str, Any]:
    if not gesture or not workflow_name:
        return {"success": False, "message": "Gesture and workflow names are required."}

    normalized_gesture = normalize_gesture_name(gesture)
    normalized_workflow = workflow_name.strip().lower().replace(" ", "_")

    workflows = load_workflows()

    if normalized_workflow in WORKFLOW_TEMPLATES:
        steps = WORKFLOW_TEMPLATES[normalized_workflow]
    else:
        source_key = normalize_gesture_name(workflow_name)
        if source_key not in workflows:
            available = ", ".join(sorted(WORKFLOW_TEMPLATES))
            return {
                "success": False,
                "message": f"Workflow '{workflow_name}' was not found. Available templates: {available}.",
            }
        steps = workflows[source_key]

    workflows[normalized_gesture] = normalize_workflow_steps(steps)
    save_workflows(workflows)
    logger.info("[System] Bound %s to workflow %s", normalized_gesture, normalized_workflow)
    return {
        "success": True,
        "message": f"{normalized_gesture} is now bound to {normalized_workflow}.",
        "gesture": normalized_gesture,
        "workflow": normalized_workflow,
    }


def list_gesture_workflows() -> Dict[str, Any]:
    workflows = load_workflows()
    if not workflows:
        return {"success": True, "message": "No gesture workflows are configured.", "workflows": {}}

    lines = ["Current gesture workflows:"]
    for gesture, steps in sorted(workflows.items(), key=lambda item: workflow_key_for_gesture(item[0])):
        action_names = ", ".join(step.get("action", "unknown") for step in steps) or "no actions"
        lines.append(f"- {gesture}: {action_names}")
    return {"success": True, "message": "\n".join(lines), "workflows": workflows}


def reset_workflow(gesture: str) -> Dict[str, Any]:
    normalized_gesture = normalize_gesture_name(gesture)
    if not normalized_gesture:
        return {"success": False, "message": "Gesture name is required."}

    workflows = load_workflows()
    default_steps = DEFAULT_GESTURE_WORKFLOWS.get(normalized_gesture)
    if default_steps:
        workflows[normalized_gesture] = normalize_workflow_steps(default_steps)
        save_workflows(workflows)
        return {"success": True, "message": f"Reset workflow for {normalized_gesture} to its default actions."}

    if normalized_gesture in workflows:
        workflows.pop(normalized_gesture, None)
        save_workflows(workflows)
        return {"success": True, "message": f"Removed custom workflow for {normalized_gesture}."}

    return {"success": False, "message": f"No workflow was found for {normalized_gesture}."}


def build_system_prompt() -> str:
    gestures = ", ".join(sorted({value for value in GESTURE_ALIASES.values()}))
    return f"""
You are STARK, a smart desktop assistant. Translate the user's request into a single valid JSON object.

Available gestures: {gestures}

Available actions:
- "launch_app": {{"app_name": "string"}}
- "open_url": {{"url": "string"}}
- "run_terminal": {{"command": "string"}}
- "type_text": {{"text": "string"}}
- "press_key": {{"key": "string"}}
- "delay": {{"seconds": number}}
- "play_media": {{"platform": "spotify"|"youtube"|"netflix", "query": "string"}}
- "search_web": {{"query": "string"}}
- "send_whatsapp_message": {{"contact": "string", "message": "string"}}
- "add_contact": {{"name": "string", "phone": "string"}}
- "update_contact": {{"name": "string", "phone": "string"}}
- "remove_contact": {{"name": "string"}}
- "list_contacts": {{}}
- "list_workflows": {{}}
- "reset_workflow": {{"gesture": "Open Palm"}}

Workflow editing tasks:
- If the user says "when I show gesture...", "change workflow", or "update workflow", return:
  {{"task": "update_workflow", "gesture": "Open Palm", "actions": [{{"action": "...", "params": {{...}}}}], "chat": "short confirmation"}}
- If the user says "bind rock sign to entertainment mode" or similar, return:
  {{"task": "bind_workflow", "gesture": "Rock Sign", "workflow": "entertainment_mode", "chat": "short confirmation"}}
- If the user wants to add, edit, delete, or show contacts, use the contact actions directly
- If the user wants to show or reset gestures/workflows, use list_workflows or reset_workflow directly

Media rules:
- Any mention of Spotify must use play_media with platform "spotify"
- Any mention of YouTube must use play_media with platform "youtube"
- Any mention of Netflix must use play_media with platform "netflix"
- Never use search_web for songs, albums, playlists, movies, or shows

WhatsApp rule:
- Commands like "message uday I will be late" must return send_whatsapp_message with contact "uday" and message "I will be late"
- Preserve multi-word contact names when they are quoted or clearly match a saved contact name

Response rules:
- Always return one JSON object
- No markdown
- No extra text
- For normal requests use:
  {{"chat": "short message", "actions": [{{"action": "...", "params": {{...}}}}]}}
- For conversational or factual answers with no automation, use:
  {{"chat": "answer here", "actions": []}}

Examples:
- User: "message uday I will be late"
  {{"chat": "Sending a WhatsApp message to uday.", "actions": [{{"action": "send_whatsapp_message", "params": {{"contact": "uday", "message": "I will be late"}}}}]}}
- User: "add contact John Doe +91 99999 99999"
  {{"chat": "Saving that contact.", "actions": [{{"action": "add_contact", "params": {{"name": "John Doe", "phone": "+91 99999 99999"}}}}]}}
- User: "show contacts"
  {{"chat": "Here are your saved contacts.", "actions": [{{"action": "list_contacts", "params": {{}}}}]}}
- User: "show gestures"
  {{"chat": "Here are your current gesture workflows.", "actions": [{{"action": "list_workflows", "params": {{}}}}]}}
- User: "When I show open palm, open VSCode and play coding music."
  {{"task": "update_workflow", "gesture": "Open Palm", "actions": [{{"action": "launch_app", "params": {{"app_name": "vscode"}}}}, {{"action": "play_media", "params": {{"platform": "youtube", "query": "coding music"}}}}], "chat": "Updating the workflow for Open Palm."}}
- User: "Bind rock sign to entertainment mode."
  {{"task": "bind_workflow", "gesture": "Rock Sign", "workflow": "entertainment_mode", "chat": "Binding Rock Sign to entertainment mode."}}
""".strip()


def normalize_reasoning_result(result: Any) -> Dict[str, Any]:
    if isinstance(result, list):
        return {"chat": "I found a set of actions to run.", "actions": normalize_workflow_steps(result)}

    if not isinstance(result, dict):
        raise ValueError("Reasoning result must be a JSON object")

    normalized = dict(result)
    if "gesture" in normalized:
        normalized["gesture"] = normalize_gesture_name(str(normalized["gesture"]))

    task = normalized.get("task")
    if task == "update_workflow":
        normalized["actions"] = normalize_workflow_steps(normalized.get("actions", []))
        normalized.setdefault("chat", f"Updating the workflow for {normalized.get('gesture', 'that gesture')}.")
    elif task == "bind_workflow":
        normalized.setdefault("chat", f"Binding {normalized.get('gesture', 'that gesture')} to a workflow.")
    else:
        normalized["actions"] = normalize_workflow_steps(normalized.get("actions", []))
        normalized.setdefault("chat", "")

    return normalized


def parse_local_instruction(query: str) -> Optional[Dict[str, Any]]:
    text = query.strip()

    whatsapp_command = parse_message_command(text)
    if whatsapp_command:
        contact = whatsapp_command["contact"]
        message = whatsapp_command["message"]
        return {
            "chat": f"Sending a WhatsApp message to {contact}.",
            "actions": [
                {
                    "action": "send_whatsapp_message",
                    "params": {"contact": contact, "message": message},
                }
            ],
        }

    add_contact_match = re.match(
        r"^(?:add|save|create)\s+contact\s+(.+?)\s+([+0-9][0-9 ()-]{7,})$",
        text,
        flags=re.IGNORECASE,
    )
    if add_contact_match:
        return {
            "chat": "Saving that contact.",
            "actions": [
                {
                    "action": "add_contact",
                    "params": {
                        "name": _strip_optional_quotes(add_contact_match.group(1)),
                        "phone": add_contact_match.group(2).strip(),
                    },
                }
            ],
        }

    update_contact_match = re.match(
        r"^(?:update|edit|change)\s+contact\s+(.+?)\s+([+0-9][0-9 ()-]{7,})$",
        text,
        flags=re.IGNORECASE,
    )
    if update_contact_match:
        return {
            "chat": "Updating that contact.",
            "actions": [
                {
                    "action": "update_contact",
                    "params": {
                        "name": _strip_optional_quotes(update_contact_match.group(1)),
                        "phone": update_contact_match.group(2).strip(),
                    },
                }
            ],
        }

    remove_contact_match = re.match(
        r"^(?:remove|delete)\s+contact\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if remove_contact_match:
        return {
            "chat": "Removing that contact.",
            "actions": [
                {
                    "action": "remove_contact",
                    "params": {"name": _strip_optional_quotes(remove_contact_match.group(1).rstrip(".!?"))},
                }
            ],
        }

    if re.match(r"^(?:show|list)(?:\s+(?:all|my))?\s+contacts$|^contacts$", text, flags=re.IGNORECASE):
        return {
            "chat": "Here are your saved contacts.",
            "actions": [{"action": "list_contacts", "params": {}}],
        }

    bind_match = re.match(
        r"^(?:bind|map)(?:\s+gesture)?\s+(.+?)\s+to\s+([a-z0-9_ .-]+?)[.!?]?$",
        text,
        flags=re.IGNORECASE,
    )
    if bind_match:
        return {
            "task": "bind_workflow",
            "gesture": normalize_gesture_name(bind_match.group(1)),
            "workflow": bind_match.group(2).strip().rstrip(".!?").replace(" ", "_"),
            "chat": "Updating that gesture binding.",
        }

    set_gesture_match = re.match(
        r"^(?:set|change|update)\s+gesture\s+(.+?)\s+(?:to|as)\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if set_gesture_match:
        gesture = normalize_gesture_name(_strip_optional_quotes(set_gesture_match.group(1)))
        actions = _parse_actions_from_text(set_gesture_match.group(2).strip())
        if actions:
            return {
                "task": "update_workflow",
                "gesture": gesture,
                "actions": actions,
                "chat": f"Updating the workflow for {gesture}.",
            }

    workflow_match = re.match(
        rf"^(?:when i show|when i do|when i use|change workflow for|update workflow for)\s+({GESTURE_PATTERN_TEXT})[,:]?\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if workflow_match:
        gesture = normalize_gesture_name(workflow_match.group(1))
        action_text = workflow_match.group(2).strip()
        actions = _parse_actions_from_text(action_text)
        if actions:
            return {
                "task": "update_workflow",
                "gesture": gesture,
                "actions": actions,
                "chat": f"Updating the workflow for {gesture}.",
            }

    if re.match(
        r"^(?:show|list)(?:\s+(?:all|my))?\s+(?:gestures|gesture workflows|workflows)$",
        text,
        flags=re.IGNORECASE,
    ):
        return {
            "chat": "Here are your current gesture workflows.",
            "actions": [{"action": "list_workflows", "params": {}}],
        }

    reset_match = re.match(
        r"^(?:reset|restore)\s+(?:gesture|workflow)\s+(.+)$",
        text,
        flags=re.IGNORECASE,
    )
    if reset_match:
        return {
            "chat": "Resetting that gesture workflow.",
            "actions": [
                {
                    "action": "reset_workflow",
                    "params": {"gesture": _strip_optional_quotes(reset_match.group(1).rstrip(".!?"))},
                }
            ],
        }

    return None


def _parse_actions_from_text(action_text: str) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    for clause in re.split(r"\s+(?:and|then)\s+", action_text.strip(), flags=re.IGNORECASE):
        step = _parse_single_action(clause.strip())
        if step:
            actions.append(step)
    return actions


def _parse_single_action(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    lower = text.lower().strip()

    open_match = re.match(r"^(?:open|launch|start)\s+(.+)$", lower)
    if open_match:
        return {"action": "launch_app", "params": {"app_name": open_match.group(1).strip()}}

    folder_match = re.match(r"^(?:create|make)\s+(?:a\s+)?folder\s+(.+)$", lower)
    if folder_match:
        return {"action": "create_folder", "params": {"value": folder_match.group(1).strip()}}

    if lower in {"open terminal", "open cmd", "open command prompt"}:
        return {"action": "open_terminal", "params": {}}

    media_match = re.match(
        r"^(?:play|watch|listen to)\s+(.+?)\s+(?:on\s+)?(youtube|spotify|netflix)$",
        lower,
    )
    if media_match:
        return {
            "action": "play_media",
            "params": {
                "query": media_match.group(1).strip(),
                "platform": media_match.group(2).strip(),
            },
        }

    generic_media_match = re.match(r"^(?:play|watch|listen to)\s+(.+)$", text, flags=re.IGNORECASE)
    if generic_media_match:
        return {
            "action": "play_media",
            "params": {
                "query": generic_media_match.group(1).strip().rstrip(".!?"),
                "platform": "youtube",
            },
        }

    if lower.startswith("read screen"):
        return {"action": "screen_read", "params": {}}

    if lower.startswith("search "):
        return {"action": "search_web", "params": {"query": text[7:].strip()}}

    return None


def _strip_optional_quotes(value: str) -> str:
    stripped = (value or "").strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1].strip()
    return stripped

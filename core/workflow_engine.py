import logging
import time
from typing import Dict, List, Tuple

from core.reasoning import normalize_gesture_name, normalize_workflow_steps


logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Executes structured workflows and protects them from rapid retriggers."""

    last_trigger_time: Dict[str, float] = {}

    def __init__(self, plugin_manager, gesture_cooldown: float = 3.0):
        self.plugin_manager = plugin_manager
        self.gesture_cooldown = gesture_cooldown

    @classmethod
    def can_trigger_workflow(cls, workflow_name: str, cooldown_seconds: float = 3.0) -> Tuple[bool, float]:
        now = time.time()
        workflow_key = normalize_gesture_name(workflow_name)
        last_time = cls.last_trigger_time.get(workflow_key, 0.0)
        elapsed = now - last_time
        if elapsed < cooldown_seconds:
            return False, cooldown_seconds - elapsed
        cls.last_trigger_time[workflow_key] = now
        return True, 0.0

    def execute_workflow(self, workflow_name: str, steps: List[dict]) -> bool:
        workflow_label = normalize_gesture_name(workflow_name)
        try:
            normalized_steps = normalize_workflow_steps(steps)
        except Exception as exc:
            logger.error("[System] Workflow '%s' is invalid: %s", workflow_label, exc)
            return False

        logger.info("[System] Running workflow: %s", workflow_label)
        for index, step in enumerate(normalized_steps, start=1):
            action = step.get("action")
            params = step.get("params", {})
            logger.info("[Action] %s(%s)", action, self._format_params(action, params))

            result = self.plugin_manager.execute_action(action, params)
            if not result.get("success"):
                logger.error(
                    "[Action] Step %s failed for %s: %s",
                    index,
                    action,
                    result.get("message", "Unknown error"),
                )
                return False

        logger.info("[System] Workflow completed: %s", workflow_label)
        return True

    @staticmethod
    def _format_params(action: str, params: dict) -> str:
        if not params:
            return ""

        if action in {"launch_app", "open_app"}:
            return params.get("app_name", "")
        if action == "play_media":
            return f"{params.get('platform', '')}, {params.get('query', '')!r}"
        if action == "send_whatsapp_message":
            return f"{params.get('contact', '')}, {params.get('message', '')!r}"

        return ", ".join(f"{key}={value!r}" for key, value in params.items())

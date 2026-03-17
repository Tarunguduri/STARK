import json
import os

from core.reasoning import build_system_prompt, normalize_reasoning_result, parse_local_instruction

try:
    from groq import Groq

    HAS_GROQ = True
except ImportError:
    Groq = None
    HAS_GROQ = False


class AIReasoningEngine:
    """Uses Groq to turn natural language into STARK actions or workflow updates."""

    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = os.environ.get("GROQ_API_KEY", "")
        self.client = Groq(api_key=api_key) if (HAS_GROQ and api_key) else None
        self.model = "llama-3.1-8b-instant"
        self.system_prompt = build_system_prompt()

    def parse_instruction(self, query: str, context: dict = None, params: dict = None) -> dict:
        context = context or {}
        params = params or {}

        local_result = parse_local_instruction(query)
        if _should_short_circuit_local(local_result):
            return local_result

        if not HAS_GROQ:
            if local_result:
                return local_result
            return {
                "chat": "Groq SDK is not installed. Running in local mode only.",
                "actions": [],
            }

        if not self.client:
            if local_result:
                return local_result
            return {
                "chat": "Groq API key is missing. Set GROQ_API_KEY to enable AI planning.",
                "actions": [],
            }

        try:
            print(f"AI Reasoning: Processing '{query}'...")
            completion = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"[CONTEXT]: {json.dumps(context)}\n\n"
                            f"[SCREEN_STATE]: {params.get('screen_state', 'None')}\n\n"
                            f"User Request: {query}"
                        ),
                    },
                ],
                model=self.model,
                temperature=0.1,
                max_tokens=600,
            )

            response_text = completion.choices[0].message.content or ""
            print(f"AI Raw Output:\n{response_text}")

            if "```json" in response_text:
                response_text = response_text.replace("```json", "").replace("```", "").strip()

            parsed = json.loads(response_text)
            return normalize_reasoning_result(parsed)
        except Exception as exc:
            print(f"Error in AI Reasoning Layer: {exc}")
            if local_result:
                return local_result
            return {"chat": "I'm sorry, I encountered an error.", "actions": []}


def _should_short_circuit_local(local_result: dict | None) -> bool:
    if not local_result:
        return False

    if local_result.get("task") in {"update_workflow", "bind_workflow"}:
        return True

    actions = local_result.get("actions", [])
    if len(actions) != 1:
        return False

    action_name = actions[0].get("action")
    return action_name in {
        "send_whatsapp_message",
        "add_contact",
        "update_contact",
        "remove_contact",
        "list_contacts",
        "list_workflows",
        "reset_workflow",
    }

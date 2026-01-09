import time
from typing import Optional, Dict, Any

from control.app_context import get_foreground_process_name
from control.actions import do_action

class Dispatcher:
    def __init__(self, config: dict, state):
        self.config = config
        self.state = state
        self.last_fire = {}

    def _cooldown_ok(self, key: str, cd_ms: int):
        now = time.time() * 1000
        last = self.last_fire.get(key, 0)
        if now - last >= cd_ms:
            self.last_fire[key] = now
            return True
        return False

    def resolve_action(self, gesture_name: str):
        b = self.config.get("bindings", {})
        per_app = b.get("per_app", {})
        glob = b.get("global", {})

        app = get_foreground_process_name()
        if app and app in per_app and gesture_name in per_app[app]:
            return per_app[app][gesture_name]
        return glob.get(gesture_name)

    def dispatch(self, gesture_name: str, cooldown_ms: int, extra_payload: Optional[Dict[str, Any]] = None):
        if not gesture_name:
            return None

        action = self.resolve_action(gesture_name)
        if not action:
            return None

        typ = action.get("type")
        is_toggle = typ in (
            "toggle_recognition", "toggle_execution",
            "toggle_camera_preview", "toggle_mouse_move_output",
            "toggle_camera_device"
        )

        if not is_toggle and not self.state.execution_enabled:
            return {"type": "blocked_execution"}

        if cooldown_ms and cooldown_ms > 0:
            if not self._cooldown_ok(gesture_name, int(cooldown_ms)):
                return None

        if extra_payload:
            merged = dict(action)
            merged.update(extra_payload)
            action = merged

        do_action(action, self.state)
        return action
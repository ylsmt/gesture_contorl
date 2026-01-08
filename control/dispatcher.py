import time
from control.app_context import get_foreground_process_name
from control.actions import do_action

class Dispatcher:
    def __init__(self, cfg: dict, state):
        self.cfg = cfg
        self.state = state
        self._last_fire = {}

    def _cooldown_ok(self, key: str, cd_ms: int) -> bool:
        now = time.time() * 1000
        last = self._last_fire.get(key, 0)
        if now - last >= cd_ms:
            self._last_fire[key] = now
            return True
        return False

    def resolve_action(self, gesture_id: str):
        b = self.cfg.get("bindings", {})
        per_app = b.get("per_app", {})
        glob = b.get("global", {})

        app = get_foreground_process_name()
        if app and app in per_app and gesture_id in per_app[app]:
            return per_app[app][gesture_id]
        return glob.get(gesture_id)

    def dispatch(self, gesture_id: str, cooldown_ms: int):
        if not gesture_id:
            return None

        action = self.resolve_action(gesture_id)
        if not action:
            return None

        # recognition_enabled 为 False 时，不派发任何动作（但 toggle_recognition 需要允许？）
        # 这里选择：识别关闭时不会产生 gesture_id，因此不需要特殊处理。
        # execution_enabled 由 actions.do_action 内部处理；但为了减少无效调用可提前拦截：
        typ = action.get("type")
        is_toggle = typ in ("toggle_recognition", "toggle_execution", "toggle_camera_preview", "toggle_mouse_move_output")

        if not is_toggle and not self.state.execution_enabled:
            return {"type": "blocked_execution"}

        if not self._cooldown_ok(gesture_id, cooldown_ms):
            return None

        do_action(action, self.state)
        return action
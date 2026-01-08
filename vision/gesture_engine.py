import time
import numpy as np
from vision.gesture_primitives import (
    classify_open_palm_fist_v_ok_thumbs,
    pinch_ratio, close_ratio
)
from vision.scroll_state import PinchScrollState

class GestureEngine:
    """
    输入：裸手关键点 + 系统状态
    输出：gesture_events（按优先级最多一个）以及可能的连续滚动动作建议
    """
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._stable = {}  # gesture_id -> count
        self._last_seen = None
        self._cool = {}    # key -> last_ms
        self.scroll = PinchScrollState()

    def _cooldown_ok(self, key: str, cd_ms: int):
        now = time.time() * 1000
        last = self._cool.get(key, 0)
        if now - last >= cd_ms:
            self._cool[key] = now
            return True
        return False

    def _stable_confirm(self, gid: str, need: int):
        if gid == self._last_seen:
            self._stable[gid] = self._stable.get(gid, 0) + 1
        else:
            self._last_seen = gid
            if gid:
                self._stable[gid] = 1
        return gid if gid and self._stable.get(gid, 0) >= need else None

    def update_bare(self, lm: np.ndarray, state):
        g = self.cfg["general"]
        pinch_thr = float(g.get("pinch_threshold_ratio", 0.33))
        close_thr = float(g.get("two_finger_close_ratio", 0.22))
        stable_frames = int(g.get("stable_frames", 3))
        cooldown_ms = int(g.get("cooldown_ms", 450))

        events = []
        scroll_action = None

        if lm is None:
            self.scroll.stop()
            return None, None, None

        # 静态分类（用于 neutral / thumbs / v等）
        raw_static = classify_open_palm_fist_v_ok_thumbs(lm, pinch_thr, close_thr)
        confirmed_static = self._stable_confirm(raw_static, stable_frames)

        # mouse_move_mode：默认规则（可完全配置化：这里先用V_SIGN作为示例条件）
        # 重要：这是“模式状态”，不是动作绑定。用户后续可通过 Gesture Catalog 改写。
        state.mouse_move_mode = (confirmed_static == "V_SIGN")

        # 1) THUMBS_UP -> gesture event（用于 toggle_recognition）
        if confirmed_static == "THUMBS_UP":
            # 使用手势条目自己的冷却/稳定参数（若有）
            cd = int(self._gesture_param("THUMBS_UP", "cooldown_ms", 1200))
            if self._cooldown_ok("THUMBS_UP", cd):
                return "THUMBS_UP", raw_static, None

        # 如果识别被关闭：这里仍返回 raw_static 供 UI 显示，但不产生事件
        if not state.recognition_enabled:
            self.scroll.stop()
            return None, raw_static, None

        # 2) 鼠标模式复合手势：右键捏合（thumb=4, middle=12）
        if state.mouse_move_mode:
            r = pinch_ratio(lm, 4, 12)
            if r < pinch_thr:
                cd = int(self._gesture_param("PINCH_RIGHT_CLICK", "cooldown_ms", 500))
                if self._cooldown_ok("PINCH_RIGHT_CLICK", cd):
                    return "PINCH_RIGHT_CLICK", raw_static, None

            # 3) 双击：index(8) 与 middle(12) 并拢
            r2 = close_ratio(lm, 8, 12)
            if r2 < close_thr:
                cd = int(self._gesture_param("INDEX_MIDDLE_DOUBLE_CLICK", "cooldown_ms", 700))
                if self._cooldown_ok("INDEX_MIDDLE_DOUBLE_CLICK", cd):
                    return "INDEX_MIDDLE_DOUBLE_CLICK", raw_static, None

            # 4) PINCH_SCROLL：thumb(4) + index(8) 捏合进入/保持滚动
            pr = pinch_ratio(lm, 4, 8)
            if pr < pinch_thr:
                # 进入或保持滚动状态：用食指指尖作为滚动控制点
                x, y = lm[8][0], lm[8][1]
                if not self.scroll.active:
                    self.scroll.start(x, y)
                dx, dy = self.scroll.delta(x, y)

                scroll_gain = float(g.get("scroll_gain", 1.6))
                dead = float(g.get("scroll_deadzone_px", 6))
                max_step = float(g.get("scroll_max_step", 120))

                # 位移比例 -> 滚动增量（dy为纵向；dx为横向）
                sv = 0
                sh = 0
                if abs(dy) >= dead:
                    sv = int(max(-max_step, min(max_step, -dy * scroll_gain)))
                if abs(dx) >= dead:
                    sh = int(max(-max_step, min(max_step, dx * scroll_gain)))

                scroll_action = {"sv": sv, "sh": sh}
                # 不直接返回 PINCH_SCROLL 作为事件（滚动是连续量），用 scroll_action 输出
                return None, raw_static, scroll_action
            else:
                self.scroll.stop()

        # 5) SWIPE_*（用轨迹方向：这里给最简实现：用 wrist(0) 最近窗口位移）
        # 为了 MVP 简化：用一阶位移近似 swipe（后续可用轨迹缓存增强）
        # 这里不做，留给你下一步补齐轨迹窗口，否则会误触。先返回静态/None。
        return None, raw_static, None

    def _gesture_param(self, gid: str, key: str, default):
        for it in self.cfg.get("gesture_catalog", []):
            if it.get("id") == gid:
                return it.get("params", {}).get(key, default)
        return default
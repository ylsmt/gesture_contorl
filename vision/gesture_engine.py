import time
import numpy as np

from vision.dynamic_track import TrackWindow
from vision.scroll_state import PinchScrollState
from vision.gesture_primitives import (
    classify_static,
    pinch_ratio,
    close_ratio,
    TIP
)

class GestureEngine:
    """
    - 静态：OPEN_PALM/FIST/THUMBS_UP/V_SIGN/INDEX_ONLY/THUMB_PINKY/OK_SIGN/UNKNOWN
    - 复合（边沿触发一次）：
        PINCH_RIGHT_CLICK：thumb+middle pinch（两指捏合）
        INDEX_MIDDLE_DOUBLE_CLICK：index+middle close（两指并拢）
    - 状态滚动：
        PINCH_SCROLL：thumb+index pinch -> 位移比例滚动（sv/sh）
    - 取消三指捏合：thumb-index pinch 与 thumb-middle pinch 同时成立时，屏蔽复合/滚动/双击
    - 动态：SWIPE_*
    - 冲突优化：
        若轨迹窗口移动明显（path_length > click_guard_move_px），屏蔽 click 类（右键/双击）
    """
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._stable_last = None
        self._stable_count = 0
        self._cool = {}

        self.scroll = PinchScrollState()
        self.track = TrackWindow(window_ms=450)

        self._unknown_count = 0

        # edge trigger states
        self._pinch_middle_down = False
        self._index_middle_close_down = False

    def _now_ms(self):
        return time.time() * 1000

    def _cooldown_ok(self, key: str, cd_ms: int):
        now = self._now_ms()
        last = self._cool.get(key, 0)
        if now - last >= cd_ms:
            self._cool[key] = now
            return True
        return False

    def _stable_confirm(self, gid: str, need: int):
        if gid == self._stable_last:
            self._stable_count += 1
        else:
            self._stable_last = gid
            self._stable_count = 1
        return gid if gid and self._stable_count >= need else None

    def _gesture_item(self, gid: str):
        for it in self.cfg.get("gesture_catalog", []):
            if it.get("id") == gid:
                return it
        return None

    def _param(self, gid: str, key: str, default):
        it = self._gesture_item(gid)
        if it:
            return it.get("params", {}).get(key, default)
        return default

    def _enable_when_ok(self, gid: str, state) -> bool:
        it = self._gesture_item(gid)
        cond = (it or {}).get("enable_when", {}) or {}
        for k, v in cond.items():
            if hasattr(state, k) and bool(getattr(state, k)) != bool(v):
                return False
        return True

    def _mouse_mode_gesture_id(self) -> str:
        for it in self.cfg.get("gesture_catalog", []):
            if it.get("default_use") == "mouse_move_mode":
                return it.get("id")
        return "V_SIGN"

    def update_bare(self, lm: np.ndarray, state):
        g = self.cfg["general"]
        self.track.set_window(int(g.get("dynamic_window_ms", 450)))

        pinch_thr = float(g.get("pinch_threshold_ratio", 0.33))
        close_thr = float(g.get("two_finger_close_ratio", 0.22))
        stable_frames = int(g.get("stable_frames", 2))
        cooldown_ms = int(g.get("cooldown_ms", 450))
        swipe_thresh = float(g.get("swipe_thresh_px", 80))

        # 关键：移动抑制 click 的阈值（越大越不容易抑制）
        click_guard_move_px = float(g.get("click_guard_move_px", 35))

        if lm is None:
            self.scroll.stop()
            self.track.reset()
            self._unknown_count = 0
            self._pinch_middle_down = False
            self._index_middle_close_down = False
            return None, None, None

        # track: index tip
        self.track.add(lm[TIP["index"]][0], lm[TIP["index"]][1])

        raw_static = classify_static(lm, pinch_thr, close_thr)
        confirmed_static = self._stable_confirm(raw_static, stable_frames)

        # mouse_move_mode：仅用于鼠标移动输出
        mm_gid = self._mouse_mode_gesture_id()
        state.mouse_move_mode = (confirmed_static == mm_gid)

        if not state.recognition_enabled:
            self.scroll.stop()
            self._unknown_count = 0
            return None, raw_static, None

        # ----- movement guard：移动明显时屏蔽 click 类 -----
        # 用轨迹窗口的路径长度判断是否在“移动中”
        moving = (self.track.length() > click_guard_move_px)

        # ----- 三指捏合检测（屏蔽用） -----
        is_pinch_index = pinch_ratio(lm, TIP["thumb"], TIP["index"]) < pinch_thr
        is_pinch_middle = pinch_ratio(lm, TIP["thumb"], TIP["middle"]) < pinch_thr
        is_three_pinch = is_pinch_index and is_pinch_middle

        if is_three_pinch:
            # 屏蔽所有“捏合相关”的复合/滚动/并拢双击，且重置边沿状态
            self.scroll.stop()
            self._pinch_middle_down = True
            self._index_middle_close_down = True
        else:
            # ----- PINCH_SCROLL：thumb+index pinch 状态滚动（保留，不受 moving 屏蔽） -----
            if self._gesture_item("PINCH_SCROLL") and self._enable_when_ok("PINCH_SCROLL", state):
                if is_pinch_index:
                    x, y = lm[TIP["index"]][0], lm[TIP["index"]][1]
                    if not self.scroll.active:
                        self.scroll.start(x, y)
                    dx, dy = self.scroll.delta(x, y)

                    scroll_gain = float(g.get("scroll_gain", 1.6))
                    dead = float(g.get("scroll_deadzone_px", 6))
                    max_step = float(g.get("scroll_max_step", 120))

                    sv = 0
                    sh = 0
                    if abs(dy) >= dead:
                        sv = int(max(-max_step, min(max_step, -dy * scroll_gain)))
                    if abs(dx) >= dead:
                        sh = int(max(-max_step, min(max_step, dx * scroll_gain)))

                    return None, raw_static, {"sv": sv, "sh": sh}
                else:
                    self.scroll.stop()

            # ----- click 类（右键/双击）：moving 时屏蔽 -----
            if not moving:
                # ----- PINCH_RIGHT_CLICK：thumb+middle pinch（边沿触发一次） -----
                if self._gesture_item("PINCH_RIGHT_CLICK") and self._enable_when_ok("PINCH_RIGHT_CLICK", state):
                    if is_pinch_middle:
                        if not self._pinch_middle_down:
                            cd = int(self._param("PINCH_RIGHT_CLICK", "cooldown_ms", 500))
                            if self._cooldown_ok("PINCH_RIGHT_CLICK", cd):
                                self._pinch_middle_down = True
                                return "PINCH_RIGHT_CLICK", raw_static, None
                        self._pinch_middle_down = True
                    else:
                        self._pinch_middle_down = False
                else:
                    # 若手势被禁用，确保状态不挂住
                    self._pinch_middle_down = False

                # ----- INDEX_MIDDLE_DOUBLE_CLICK：index+middle close（边沿触发一次） -----
                if self._gesture_item("INDEX_MIDDLE_DOUBLE_CLICK") and self._enable_when_ok("INDEX_MIDDLE_DOUBLE_CLICK", state):
                    is_close = close_ratio(lm, TIP["index"], TIP["middle"]) < close_thr
                    if is_close:
                        if not self._index_middle_close_down:
                            cd = int(self._param("INDEX_MIDDLE_DOUBLE_CLICK", "cooldown_ms", 700))
                            if self._cooldown_ok("INDEX_MIDDLE_DOUBLE_CLICK", cd):
                                self._index_middle_close_down = True
                                return "INDEX_MIDDLE_DOUBLE_CLICK", raw_static, None
                        self._index_middle_close_down = True
                    else:
                        self._index_middle_close_down = False
                else:
                    self._index_middle_close_down = False
            else:
                # moving 时：不允许 click，且复位边沿状态，避免滑动中误触发
                self._pinch_middle_down = False
                self._index_middle_close_down = False

        # ----- 静态事件（可绑定；默认绑定为空） -----
        if confirmed_static and self._gesture_item(confirmed_static) and self._enable_when_ok(confirmed_static, state):
            cd = int(self._param(confirmed_static, "cooldown_ms", cooldown_ms))
            if self._cooldown_ok(confirmed_static, cd):
                return confirmed_static, raw_static, None

        # ----- 动态 SWIPE_* -----
        dx, dy = self.track.delta()
        if abs(dx) > abs(dy) and abs(dx) > swipe_thresh:
            gid = "SWIPE_RIGHT" if dx > 0 else "SWIPE_LEFT"
            if self._gesture_item(gid) and self._enable_when_ok(gid, state) and self._cooldown_ok(gid, cooldown_ms):
                self.track.reset()
                return gid, raw_static, None

        if abs(dy) > abs(dx) and abs(dy) > swipe_thresh:
            gid = "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"
            if self._gesture_item(gid) and self._enable_when_ok(gid, state) and self._cooldown_ok(gid, cooldown_ms):
                self.track.reset()
                return gid, raw_static, None

        # ----- UNKNOWN -----
        if raw_static is None and self._gesture_item("UNKNOWN") and self._enable_when_ok("UNKNOWN", state):
            self._unknown_count += 1
            need = int(self._param("UNKNOWN", "stable_frames", 3))
            if self._unknown_count >= need:
                cd = int(self._param("UNKNOWN", "cooldown_ms", 800))
                if self._cooldown_ok("UNKNOWN", cd):
                    self._unknown_count = 0
                    return "UNKNOWN", raw_static, None
        else:
            self._unknown_count = 0

        return None, raw_static, None

    def update_glove(self, feats, state):
        g = self.cfg["general"]
        self.track.set_window(int(g.get("dynamic_window_ms", 450)))
        cooldown_ms = int(g.get("cooldown_ms", 450))
        swipe_thresh = float(g.get("swipe_thresh_px", 80))

        if feats is None or feats.center is None:
            self.scroll.stop()
            self.track.reset()
            return None, None, None

        cx, cy = feats.center
        self.track.add(cx, cy)

        state.mouse_move_mode = (len(feats.fingertips) >= 2)

        if not state.recognition_enabled:
            self.scroll.stop()
            return None, "GLOVE_TRACKING", None

        dx, dy = self.track.delta()
        if abs(dx) > abs(dy) and abs(dx) > swipe_thresh:
            gid = "SWIPE_RIGHT" if dx > 0 else "SWIPE_LEFT"
            if self._gesture_item(gid) and self._enable_when_ok(gid, state) and self._cooldown_ok(gid, cooldown_ms):
                self.track.reset()
                return gid, "GLOVE_TRACKING", None

        if abs(dy) > abs(dx) and abs(dy) > swipe_thresh:
            gid = "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"
            if self._gesture_item(gid) and self._enable_when_ok(gid, state) and self._cooldown_ok(gid, cooldown_ms):
                self.track.reset()
                return gid, "GLOVE_TRACKING", None

        return None, "GLOVE_TRACKING", None
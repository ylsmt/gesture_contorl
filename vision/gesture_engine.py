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
      click门控：
        * pinch/close 必须持续 N 帧（click_hold_frames）
        * 平均速度必须低于阈值（click_max_speed_px_per_s）
        * 移动明显（path_length>click_guard_move_px）时屏蔽 click
    - 状态滚动：
        PINCH_SCROLL：thumb+index pinch -> 位移比例滚动（sv/sh）
    - 取消三指捏合：thumb-index pinch 与 thumb-middle pinch 同时成立时，屏蔽复合/滚动/双击
    - 动态：SWIPE_*
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

        # hold counters (持续N帧门控)
        self._pinch_middle_hold = 0
        self._index_middle_close_hold = 0

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

    def _avg_speed_px_per_s(self) -> float:
        """
        基于 track 内点计算平均速度（px/s）。
        TrackWindow pts: (t_ms, x, y)
        """
        pts = self.track.pts
        if len(pts) < 6:
            return 0.0
        t0, x0, y0 = pts[0]
        t1, x1, y1 = pts[-1]
        dt = (t1 - t0) / 1000.0
        if dt <= 1e-6:
            return 0.0
        dist = float(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5)
        return dist / dt

    def update_bare(self, lm: np.ndarray, state):
        g = self.cfg["general"]
        self.track.set_window(int(g.get("dynamic_window_ms", 450)))

        pinch_thr = float(g.get("pinch_threshold_ratio", 0.33))
        close_thr = float(g.get("two_finger_close_ratio", 0.22))
        stable_frames = int(g.get("stable_frames", 2))
        cooldown_ms = int(g.get("cooldown_ms", 450))
        swipe_thresh = float(g.get("swipe_thresh_px", 80))

        # click门控参数
        click_guard_move_px = float(g.get("click_guard_move_px", 35))
        click_hold_frames = int(g.get("click_hold_frames", 2))
        click_max_speed = float(g.get("click_max_speed_px_per_s", 650))

        if lm is None:
            self.scroll.stop()
            self.track.reset()
            self._unknown_count = 0
            self._pinch_middle_down = False
            self._index_middle_close_down = False
            self._pinch_middle_hold = 0
            self._index_middle_close_hold = 0
            return None, None, None

        # track: index tip
        self.track.add(lm[TIP["index"]][0], lm[TIP["index"]][1])

        rules_cfg = self.cfg.get("general", {}).get("finger_rules", {})
        raw_static = classify_static(lm, pinch_thr, close_thr, rules_cfg=rules_cfg)
        confirmed_static = self._stable_confirm(raw_static, stable_frames)

        # mouse_move_mode：仅用于鼠标移动输出
        mm_gid = self._mouse_mode_gesture_id()
        state.mouse_move_mode = (confirmed_static == mm_gid)

        if not state.recognition_enabled:
            self.scroll.stop()
            self._unknown_count = 0
            return None, raw_static, None

        # movement guard：移动明显时屏蔽 click
        moving = (self.track.length() > click_guard_move_px)

        # speed gate：速度过快时屏蔽 click
        speed = self._avg_speed_px_per_s()
        slow_enough = (speed <= click_max_speed)

        # 三指捏合屏蔽
        is_pinch_index = pinch_ratio(lm, TIP["thumb"], TIP["index"]) < pinch_thr
        is_pinch_middle = pinch_ratio(lm, TIP["thumb"], TIP["middle"]) < pinch_thr
        is_three_pinch = is_pinch_index and is_pinch_middle

        if is_three_pinch:
            self.scroll.stop()
            # 直接把 hold/down 置为“按下”，避免松开瞬间边沿触发
            self._pinch_middle_down = True
            self._index_middle_close_down = True
            self._pinch_middle_hold = 0
            self._index_middle_close_hold = 0
        else:
            # PINCH_SCROLL：thumb+index pinch 状态滚动（保留，不受 click 门控影响）
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

            # click类门控：必须“不在移动中”且“足够慢”
            click_allowed = (not moving) and slow_enough

            if click_allowed:
                # --- PINCH_RIGHT_CLICK：thumb+middle pinch（持续N帧 + 边沿触发） ---
                if self._gesture_item("PINCH_RIGHT_CLICK") and self._enable_when_ok("PINCH_RIGHT_CLICK", state):
                    if is_pinch_middle:
                        self._pinch_middle_hold += 1
                        if self._pinch_middle_hold >= click_hold_frames:
                            if not self._pinch_middle_down:
                                cd = int(self._param("PINCH_RIGHT_CLICK", "cooldown_ms", 500))
                                if self._cooldown_ok("PINCH_RIGHT_CLICK", cd):
                                    self._pinch_middle_down = True
                                    return "PINCH_RIGHT_CLICK", raw_static, None
                            self._pinch_middle_down = True
                    else:
                        self._pinch_middle_down = False
                        self._pinch_middle_hold = 0
                else:
                    self._pinch_middle_down = False
                    self._pinch_middle_hold = 0

                # --- INDEX_MIDDLE_DOUBLE_CLICK：index+middle close（持续N帧 + 边沿触发） ---
                if self._gesture_item("INDEX_MIDDLE_DOUBLE_CLICK") and self._enable_when_ok("INDEX_MIDDLE_DOUBLE_CLICK", state):
                    is_close = close_ratio(lm, TIP["index"], TIP["middle"]) < close_thr
                    if is_close:
                        self._index_middle_close_hold += 1
                        if self._index_middle_close_hold >= click_hold_frames:
                            if not self._index_middle_close_down:
                                cd = int(self._param("INDEX_MIDDLE_DOUBLE_CLICK", "cooldown_ms", 700))
                                if self._cooldown_ok("INDEX_MIDDLE_DOUBLE_CLICK", cd):
                                    self._index_middle_close_down = True
                                    return "INDEX_MIDDLE_DOUBLE_CLICK", raw_static, None
                            self._index_middle_close_down = True
                    else:
                        self._index_middle_close_down = False
                        self._index_middle_close_hold = 0
                else:
                    self._index_middle_close_down = False
                    self._index_middle_close_hold = 0

            else:
                # 不允许 click：复位 click 状态，避免滑动/快速动作误触发
                self._pinch_middle_down = False
                self._index_middle_close_down = False
                self._pinch_middle_hold = 0
                self._index_middle_close_hold = 0

        # 静态事件（可绑定）
        if confirmed_static and self._gesture_item(confirmed_static) and self._enable_when_ok(confirmed_static, state):
            cd = int(self._param(confirmed_static, "cooldown_ms", cooldown_ms))
            if self._cooldown_ok(confirmed_static, cd):
                return confirmed_static, raw_static, None

        # 动态 SWIPE_*
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

        # UNKNOWN
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
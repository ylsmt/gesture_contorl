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
    这是“调试增强版”：
    - 不改变你原有判定逻辑
    - 额外返回 debug dict（包含关键数值与 blocked_reason）
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

        # hold counters
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

        click_guard_move_px = float(g.get("click_guard_move_px", 35))
        click_hold_frames = int(g.get("click_hold_frames", 2))
        click_max_speed = float(g.get("click_max_speed_px_per_s", 650))

        debug = {
            "note": "engine_debug",
            "recognition_enabled": bool(getattr(state, "recognition_enabled", True)),
            "mouse_move_mode": bool(getattr(state, "mouse_move_mode", False)),
            "stable_frames": stable_frames,
            "cooldown_ms": cooldown_ms,
            "pinch_thr_ratio": pinch_thr,
            "close_thr_ratio": close_thr,
            "swipe_thresh_px": swipe_thresh,
            "click_guard_move_px": click_guard_move_px,
            "click_hold_frames": click_hold_frames,
            "click_max_speed": click_max_speed,
            "blocked_reason": ""
        }

        if lm is None:
            self.scroll.stop()
            self.track.reset()
            self._unknown_count = 0
            self._pinch_middle_down = False
            self._index_middle_close_down = False
            self._pinch_middle_hold = 0
            self._index_middle_close_hold = 0
            debug["blocked_reason"] = "no_landmarks"
            return None, None, None, debug

        # track update
        self.track.add(lm[TIP["index"]][0], lm[TIP["index"]][1])

        rules_cfg = self.cfg.get("general", {}).get("finger_rules", {})
        raw_static = classify_static(lm, pinch_thr, close_thr, rules_cfg=rules_cfg)
        confirmed_static = self._stable_confirm(raw_static, stable_frames)

        mm_gid = self._mouse_mode_gesture_id()
        state.mouse_move_mode = (confirmed_static == mm_gid)

        debug.update({
            "raw_static": raw_static,
            "confirmed_static": confirmed_static,
            "mouse_move_mode_gesture": mm_gid,
            "mouse_move_mode": bool(state.mouse_move_mode),
            "stable_last": self._stable_last,
            "stable_count": self._stable_count
        })

        if not state.recognition_enabled:
            self.scroll.stop()
            self._unknown_count = 0
            debug["blocked_reason"] = "recognition_disabled"
            return None, raw_static, None, debug

        # gating signals
        path_len = float(self.track.length())
        moving = (path_len > click_guard_move_px)
        speed = float(self._avg_speed_px_per_s())
        slow_enough = (speed <= click_max_speed)

        # pinch/close ratios
        pr_index = float(pinch_ratio(lm, TIP["thumb"], TIP["index"]))
        pr_middle = float(pinch_ratio(lm, TIP["thumb"], TIP["middle"]))
        cr_im = float(close_ratio(lm, TIP["index"], TIP["middle"]))

        is_pinch_index = pr_index < pinch_thr
        is_pinch_middle = pr_middle < pinch_thr
        is_three_pinch = is_pinch_index and is_pinch_middle

        dx, dy = self.track.delta()

        debug.update({
            "path_len": round(path_len, 2),
            "moving": moving,
            "avg_speed": round(speed, 2),
            "slow_enough": slow_enough,
            "pinch_thumb_index": round(pr_index, 3),
            "pinch_thumb_middle": round(pr_middle, 3),
            "close_index_middle": round(cr_im, 3),
            "is_pinch_index": is_pinch_index,
            "is_pinch_middle": is_pinch_middle,
            "three_pinch": is_three_pinch,
            "dx": round(dx, 1),
            "dy": round(dy, 1),
            "scroll_active": bool(self.scroll.active),
            "pinch_middle_down": bool(self._pinch_middle_down),
            "pinch_middle_hold": int(self._pinch_middle_hold),
            "close_down": bool(self._index_middle_close_down),
            "close_hold": int(self._index_middle_close_hold)
        })

        # 三指捏合屏蔽
        if is_three_pinch:
            self.scroll.stop()
            self._pinch_middle_down = True
            self._index_middle_close_down = True
            self._pinch_middle_hold = 0
            self._index_middle_close_hold = 0
            debug["blocked_reason"] = "three_pinch_block"
        else:
            # PINCH_SCROLL
            if self._gesture_item("PINCH_SCROLL") and self._enable_when_ok("PINCH_SCROLL", state):
                if is_pinch_index:
                    x, y = lm[TIP["index"]][0], lm[TIP["index"]][1]
                    if not self.scroll.active:
                        self.scroll.start(x, y)
                    dxs, dys = self.scroll.delta(x, y)

                    scroll_gain = float(g.get("scroll_gain", 1.6))
                    dead = float(g.get("scroll_deadzone_px", 6))
                    max_step = float(g.get("scroll_max_step", 120))

                    sv = 0
                    sh = 0
                    if abs(dys) >= dead:
                        sv = int(max(-max_step, min(max_step, -dys * scroll_gain)))
                    if abs(dxs) >= dead:
                        sh = int(max(-max_step, min(max_step, dxs * scroll_gain)))

                    debug["scroll_active"] = True
                    debug["scroll_dx"] = round(dxs, 1)
                    debug["scroll_dy"] = round(dys, 1)
                    debug["scroll_sv"] = sv
                    debug["scroll_sh"] = sh
                    debug["blocked_reason"] = "scroll_active"
                    return None, raw_static, {"sv": sv, "sh": sh}, debug
                else:
                    self.scroll.stop()
                    debug["scroll_active"] = False

            click_allowed = (not moving) and slow_enough
            debug["click_allowed"] = click_allowed

            if click_allowed:
                # PINCH_RIGHT_CLICK
                if self._gesture_item("PINCH_RIGHT_CLICK") and self._enable_when_ok("PINCH_RIGHT_CLICK", state):
                    if is_pinch_middle:
                        self._pinch_middle_hold += 1
                        if self._pinch_middle_hold >= click_hold_frames:
                            if not self._pinch_middle_down:
                                cd = int(self._param("PINCH_RIGHT_CLICK", "cooldown_ms", 500))
                                if self._cooldown_ok("PINCH_RIGHT_CLICK", cd):
                                    self._pinch_middle_down = True
                                    debug["event"] = "PINCH_RIGHT_CLICK"
                                    debug["blocked_reason"] = ""
                                    return "PINCH_RIGHT_CLICK", raw_static, None, debug
                                else:
                                    debug["blocked_reason"] = "cooldown_pinchr"
                            self._pinch_middle_down = True
                        else:
                            debug["blocked_reason"] = "hold_pinchr_not_enough"
                    else:
                        self._pinch_middle_down = False
                        self._pinch_middle_hold = 0

                # INDEX_MIDDLE_DOUBLE_CLICK
                if self._gesture_item("INDEX_MIDDLE_DOUBLE_CLICK") and self._enable_when_ok("INDEX_MIDDLE_DOUBLE_CLICK", state):
                    is_close = (cr_im < close_thr)
                    if is_close:
                        self._index_middle_close_hold += 1
                        if self._index_middle_close_hold >= click_hold_frames:
                            if not self._index_middle_close_down:
                                cd = int(self._param("INDEX_MIDDLE_DOUBLE_CLICK", "cooldown_ms", 700))
                                if self._cooldown_ok("INDEX_MIDDLE_DOUBLE_CLICK", cd):
                                    self._index_middle_close_down = True
                                    debug["event"] = "INDEX_MIDDLE_DOUBLE_CLICK"
                                    debug["blocked_reason"] = ""
                                    return "INDEX_MIDDLE_DOUBLE_CLICK", raw_static, None, debug
                                else:
                                    debug["blocked_reason"] = "cooldown_double"
                            self._index_middle_close_down = True
                        else:
                            debug["blocked_reason"] = "hold_double_not_enough"
                    else:
                        self._index_middle_close_down = False
                        self._index_middle_close_hold = 0
            else:
                # 不允许 click：记录原因
                if moving:
                    debug["blocked_reason"] = "click_blocked_moving"
                elif not slow_enough:
                    debug["blocked_reason"] = "click_blocked_speed"
                self._pinch_middle_down = False
                self._index_middle_close_down = False
                self._pinch_middle_hold = 0
                self._index_middle_close_hold = 0

        # 静态事件
        if confirmed_static and self._gesture_item(confirmed_static) and self._enable_when_ok(confirmed_static, state):
            cd = int(self._param(confirmed_static, "cooldown_ms", cooldown_ms))
            if self._cooldown_ok(confirmed_static, cd):
                debug["event"] = confirmed_static
                debug["blocked_reason"] = ""
                return confirmed_static, raw_static, None, debug
            else:
                debug["blocked_reason"] = f"cooldown_static:{confirmed_static}"

        # SWIPE
        if abs(dx) > abs(dy) and abs(dx) > swipe_thresh:
            gid = "SWIPE_RIGHT" if dx > 0 else "SWIPE_LEFT"
            if self._gesture_item(gid) and self._enable_when_ok(gid, state):
                if self._cooldown_ok(gid, cooldown_ms):
                    self.track.reset()
                    debug["event"] = gid
                    debug["blocked_reason"] = ""
                    return gid, raw_static, None, debug
                else:
                    debug["blocked_reason"] = "cooldown_swipe"

        if abs(dy) > abs(dx) and abs(dy) > swipe_thresh:
            gid = "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"
            if self._gesture_item(gid) and self._enable_when_ok(gid, state):
                if self._cooldown_ok(gid, cooldown_ms):
                    self.track.reset()
                    debug["event"] = gid
                    debug["blocked_reason"] = ""
                    return gid, raw_static, None, debug
                else:
                    debug["blocked_reason"] = "cooldown_swipe"

        # UNKNOWN
        if raw_static is None and self._gesture_item("UNKNOWN") and self._enable_when_ok("UNKNOWN", state):
            self._unknown_count += 1
            need = int(self._param("UNKNOWN", "stable_frames", 3))
            debug["unknown_count"] = self._unknown_count
            debug["unknown_need"] = need
            if self._unknown_count >= need:
                cd = int(self._param("UNKNOWN", "cooldown_ms", 800))
                if self._cooldown_ok("UNKNOWN", cd):
                    self._unknown_count = 0
                    debug["event"] = "UNKNOWN"
                    debug["blocked_reason"] = ""
                    return "UNKNOWN", raw_static, None, debug
                else:
                    debug["blocked_reason"] = "cooldown_unknown"
        else:
            self._unknown_count = 0

        # no event
        if not debug["blocked_reason"]:
            debug["blocked_reason"] = "no_event_matched"
        return None, raw_static, None, debug

    def update_glove(self, feats, state):
        # 同样返回 debug
        g = self.cfg["general"]
        self.track.set_window(int(g.get("dynamic_window_ms", 450)))
        cooldown_ms = int(g.get("cooldown_ms", 450))
        swipe_thresh = float(g.get("swipe_thresh_px", 80))

        debug = {
            "note": "glove_debug",
            "recognition_enabled": bool(getattr(state, "recognition_enabled", True)),
            "blocked_reason": ""
        }

        if feats is None or feats.center is None:
            self.scroll.stop()
            self.track.reset()
            debug["blocked_reason"] = "no_glove_center"
            return None, None, None, debug

        cx, cy = feats.center
        self.track.add(cx, cy)
        state.mouse_move_mode = (len(feats.fingertips) >= 2)

        if not state.recognition_enabled:
            self.scroll.stop()
            debug["blocked_reason"] = "recognition_disabled"
            return None, "GLOVE_TRACKING", None, debug

        dx, dy = self.track.delta()
        debug.update({"dx": dx, "dy": dy, "fingertips": len(feats.fingertips)})

        if abs(dx) > abs(dy) and abs(dx) > swipe_thresh:
            gid = "SWIPE_RIGHT" if dx > 0 else "SWIPE_LEFT"
            if self._gesture_item(gid) and self._enable_when_ok(gid, state):
                if self._cooldown_ok(gid, cooldown_ms):
                    self.track.reset()
                    debug["event"] = gid
                    debug["blocked_reason"] = ""
                    return gid, "GLOVE_TRACKING", None, debug
                debug["blocked_reason"] = "cooldown_swipe"

        if abs(dy) > abs(dx) and abs(dy) > swipe_thresh:
            gid = "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"
            if self._gesture_item(gid) and self._enable_when_ok(gid, state):
                if self._cooldown_ok(gid, cooldown_ms):
                    self.track.reset()
                    debug["event"] = gid
                    debug["blocked_reason"] = ""
                    return gid, "GLOVE_TRACKING", None, debug
                debug["blocked_reason"] = "cooldown_swipe"

        if not debug["blocked_reason"]:
            debug["blocked_reason"] = "no_event_matched"
        return None, "GLOVE_TRACKING", None, debug
import time
import numpy as np
from vision.dynamic_track import TrackWindow
from vision.gesture_primitives import (
    classify_open_palm_fist_v_ok_thumbs,
    pinch_ratio, close_ratio, palm_width
)
from vision.scroll_state import PinchScrollState

class GestureEngine:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self._stable_last = None
        self._stable_count = 0
        self._cool = {}
        self.scroll = PinchScrollState()
        self.track = TrackWindow(window_ms=450)

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
        # 支持的条件键：mouse_move_mode / recognition_enabled / execution_enabled / mouse_move_output_enabled
        for k, v in cond.items():
            if not hasattr(state, k):
                continue
            if bool(getattr(state, k)) != bool(v):
                return False
        return True

    def _mouse_mode_gesture_id(self) -> str:
        # 从 gesture_catalog 找 default_use == "mouse_move_mode"
        for it in self.cfg.get("gesture_catalog", []):
            if it.get("default_use") == "mouse_move_mode":
                return it.get("id")
        return "V_SIGN"

    def update_bare(self, lm: np.ndarray, state):
        g = self.cfg["general"]
        self.track.set_window(int(g.get("dynamic_window_ms", 450)) if "dynamic_window_ms" in g else 450)

        pinch_thr = float(g.get("pinch_threshold_ratio", 0.33))
        close_thr = float(g.get("two_finger_close_ratio", 0.22))
        stable_frames = int(g.get("stable_frames", 3))
        cooldown_ms = int(g.get("cooldown_ms", 450))

        if lm is None:
            self.scroll.stop()
            self.track.reset()
            return None, None, None

        # update track with index tip
        self.track.add(lm[8][0], lm[8][1])

        raw_static = classify_open_palm_fist_v_ok_thumbs(lm, pinch_thr, close_thr)
        confirmed_static = self._stable_confirm(raw_static, stable_frames)

        # 配置化鼠标移动模式：某个手势确认后 mouse_move_mode=True
        mm_gid = self._mouse_mode_gesture_id()
        state.mouse_move_mode = (confirmed_static == mm_gid)

        # 若识别关闭：不产生事件/滚动
        if not state.recognition_enabled:
            self.scroll.stop()
            return None, raw_static, None

        # 1) 静态事件（例如 THUMBS_UP）
        if confirmed_static:
            it = self._gesture_item(confirmed_static)
            if it and it.get("type") == "static" and self._enable_when_ok(confirmed_static, state):
                cd = int(self._param(confirmed_static, "cooldown_ms", 1200 if confirmed_static == "THUMBS_UP" else cooldown_ms))
                if self._cooldown_ok(confirmed_static, cd):
                    return confirmed_static, raw_static, None

        # 2) PINCH_SCROLL：thumb(4)+index(8)
        if state.mouse_move_mode and self._enable_when_ok("PINCH_SCROLL", state):
            pr = pinch_ratio(lm, 4, 8)
            if pr < pinch_thr:
                x, y = lm[8][0], lm[8][1]
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

        # 3) 复合：右键 pinch（thumb+middle）
        if state.mouse_move_mode and self._enable_when_ok("PINCH_RIGHT_CLICK", state):
            r = pinch_ratio(lm, 4, 12)
            if r < pinch_thr:
                cd = int(self._param("PINCH_RIGHT_CLICK", "cooldown_ms", 500))
                if self._cooldown_ok("PINCH_RIGHT_CLICK", cd):
                    return "PINCH_RIGHT_CLICK", raw_static, None

        # 4) 复合：双击（index+middle close）
        if state.mouse_move_mode and self._enable_when_ok("INDEX_MIDDLE_DOUBLE_CLICK", state):
            r2 = close_ratio(lm, 8, 12)
            if r2 < close_thr:
                cd = int(self._param("INDEX_MIDDLE_DOUBLE_CLICK", "cooldown_ms", 700))
                if self._cooldown_ok("INDEX_MIDDLE_DOUBLE_CLICK", cd):
                    return "INDEX_MIDDLE_DOUBLE_CLICK", raw_static, None

        # 5) 动态 SWIPE_*（使用 track delta）
        dx, dy = self.track.delta()
        swipe_thresh = float(g.get("swipe_thresh_px", 120))  # 新增配置项，缺省120
        if abs(dx) > abs(dy) and abs(dx) > swipe_thresh:
            gid = "SWIPE_RIGHT" if dx > 0 else "SWIPE_LEFT"
            if self._enable_when_ok(gid, state) and self._cooldown_ok(gid, cooldown_ms):
                self.track.reset()
                return gid, raw_static, None
        if abs(dy) > abs(dx) and abs(dy) > swipe_thresh:
            gid = "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"
            if self._enable_when_ok(gid, state) and self._cooldown_ok(gid, cooldown_ms):
                self.track.reset()
                return gid, raw_static, None

        return None, raw_static, None

    def update_glove(self, feats, state):
        """
        方案C：先用 center 做轨迹 & mouse move；fingertips 做粗手势（可后续增强）
        feats: GloveFeatures
        """
        g = self.cfg["general"]
        self.track.set_window(int(g.get("dynamic_window_ms", 450)) if "dynamic_window_ms" in g else 450)
        cooldown_ms = int(g.get("cooldown_ms", 450))

        if feats is None or feats.center is None:
            self.scroll.stop()
            self.track.reset()
            return None, None, None

        cx, cy = feats.center
        self.track.add(cx, cy)

        # 手套模式 mouse_move_mode：默认用 V_SIGN 类似的“指数量==2”粗判
        # 这里先简化：>=2 指尖则认为移动模式（用户后续可在手势字典里改为别的）
        state.mouse_move_mode = (len(feats.fingertips) >= 2)

        if not state.recognition_enabled:
            self.scroll.stop()
            return None, "GLOVE_TRACKING", None

        # SWIPE_* 基于 center 轨迹
        dx, dy = self.track.delta()
        swipe_thresh = float(g.get("swipe_thresh_px", 120))
        if abs(dx) > abs(dy) and abs(dx) > swipe_thresh:
            gid = "SWIPE_RIGHT" if dx > 0 else "SWIPE_LEFT"
            if self._enable_when_ok(gid, state) and self._cooldown_ok(gid, cooldown_ms):
                self.track.reset()
                return gid, "GLOVE_TRACKING", None
        if abs(dy) > abs(dx) and abs(dy) > swipe_thresh:
            gid = "SWIPE_DOWN" if dy > 0 else "SWIPE_UP"
            if self._enable_when_ok(gid, state) and self._cooldown_ok(gid, cooldown_ms):
                self.track.reset()
                return gid, "GLOVE_TRACKING", None

        return None, "GLOVE_TRACKING", None
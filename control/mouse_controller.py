from dataclasses import dataclass
import pyautogui

@dataclass
class MouseParams:
    smoothing: float = 0.35
    sensitivity: float = 1.0
    deadzone_px: int = 2

class MouseController:
    def __init__(self, params: MouseParams):
        self.params = params
        self._sx = None
        self._sy = None
        self._sw, self._sh = pyautogui.size()

    def update(self, params: MouseParams):
        self.params = params

    def reset(self):
        self._sx = None
        self._sy = None

    def compute_target(self, x_px: float, y_px: float, frame_w: int, frame_h: int):
        if frame_w <= 1 or frame_h <= 1:
            return None

        tx = (x_px / frame_w) * self._sw
        ty = (y_px / frame_h) * self._sh

        cx, cy = self._sw / 2, self._sh / 2
        tx = cx + (tx - cx) * float(self.params.sensitivity)
        ty = cy + (ty - cy) * float(self.params.sensitivity)

        tx = max(0, min(self._sw - 1, tx))
        ty = max(0, min(self._sh - 1, ty))

        if self._sx is None:
            self._sx, self._sy = tx, ty
        else:
            a = float(self.params.smoothing)
            self._sx = self._sx * a + tx * (1 - a)
            self._sy = self._sy * a + ty * (1 - a)

        cur = pyautogui.position()
        if abs(self._sx - cur.x) < self.params.deadzone_px and abs(self._sy - cur.y) < self.params.deadzone_px:
            return None
        return (self._sx, self._sy)
import time
import numpy as np

class TrackWindow:
    def __init__(self, window_ms=450):
        self.window_ms = int(window_ms)
        self.pts = []  # (t_ms, x, y)

    def set_window(self, window_ms: int):
        self.window_ms = int(window_ms)

    def reset(self):
        self.pts.clear()

    def add(self, x, y):
        now = time.time() * 1000
        self.pts.append((now, float(x), float(y)))
        cutoff = now - self.window_ms
        while self.pts and self.pts[0][0] < cutoff:
            self.pts.pop(0)

    def delta(self):
        if len(self.pts) < 6:
            return 0.0, 0.0
        _, x0, y0 = self.pts[0]
        _, x1, y1 = self.pts[-1]
        return x1 - x0, y1 - y0

    def length(self):
        if len(self.pts) < 2:
            return 0.0
        arr = np.array([(x, y) for _, x, y in self.pts], dtype=np.float32)
        dif = np.diff(arr, axis=0)
        seg = np.linalg.norm(dif, axis=1)
        return float(seg.sum())
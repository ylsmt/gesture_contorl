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

    def direction_consistency(self, axis: str = "x") -> float:
        """
        计算轨迹在指定轴向上的方向一致性。
        返回值范围 [0, 1]：1表示完全单向，0表示来回摆动。
        
        axis: "x" 或 "y"
        """
        if len(self.pts) < 3:
            return 0.0
        
        arr = np.array([(x, y) for _, x, y in self.pts], dtype=np.float32)
        if axis == "x":
            vals = arr[:, 0]
        else:
            vals = arr[:, 1]
        
        diffs = np.diff(vals)
        if len(diffs) == 0:
            return 0.0
        
        # 统计同向移动的占比
        positive = np.sum(diffs > 0)
        negative = np.sum(diffs < 0)
        total = positive + negative
        if total == 0:
            return 0.0
        
        # 主方向占比
        return float(max(positive, negative) / total)

    def is_unidirectional(self, axis: str, threshold: float = 0.75) -> bool:
        """
        判断轨迹在指定轴向是否是单向的（一致性 >= threshold）。
        """
        return self.direction_consistency(axis) >= threshold
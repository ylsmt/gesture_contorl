import numpy as np

def resample_polyline(points: np.ndarray, n=64) -> np.ndarray:
    if points is None or len(points) < 2:
        return None
    pts = points.astype(np.float32)
    dif = np.diff(pts, axis=0)
    seg = np.linalg.norm(dif, axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    total = float(s[-1])
    if total < 1e-6:
        return np.repeat(pts[:1], n, axis=0)

    target = np.linspace(0.0, total, n, dtype=np.float32)
    out = []
    j = 0
    for t in target:
        while j < len(s) - 2 and s[j + 1] < t:
            j += 1
        s0, s1 = s[j], s[j + 1]
        p0, p1 = pts[j], pts[j + 1]
        if s1 - s0 < 1e-6:
            out.append(p0)
        else:
            a = (t - s0) / (s1 - s0)
            out.append(p0 * (1 - a) + p1 * a)
    return np.stack(out, axis=0)

def normalize_trajectory(points: np.ndarray, n=64) -> np.ndarray:
    rs = resample_polyline(points, n=n)
    if rs is None:
        return None
    center = rs.mean(axis=0, keepdims=True)
    rs = rs - center
    scale = np.sqrt((rs ** 2).sum(axis=1).mean())
    if scale < 1e-6:
        scale = 1.0
    rs = rs / scale
    return rs.astype(np.float32)

def template_distance(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None or a.shape != b.shape:
        return 1e9
    return float(np.linalg.norm(a - b, axis=1).mean())
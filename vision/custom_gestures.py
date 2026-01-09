import numpy as np
from vision.trajectory import normalize_trajectory, template_distance

class CustomGestureManager:
    """
    cfg["custom_gestures"] = [
      {"id":"MY_CIRCLE", "mode":"bare", "type":"dynamic_template", "template":[[x,y]...64]}
    ]
    """
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.cfg.setdefault("custom_gestures", [])

    def list_ids(self, mode=None):
        out = []
        for g in self.cfg.get("custom_gestures", []):
            if g.get("type") != "dynamic_template":
                continue
            if mode and g.get("mode") not in (mode, "both"):
                continue
            out.append(g.get("id"))
        return [x for x in out if x]

    def add_template(self, gid: str, mode: str, raw_points: np.ndarray) -> bool:
        norm = normalize_trajectory(raw_points, n=64)
        if norm is None:
            return False
        entry = {"id": gid, "mode": mode, "type": "dynamic_template", "template": norm.tolist()}
        # 覆盖同名
        self.cfg["custom_gestures"] = [x for x in self.cfg["custom_gestures"] if x.get("id") != gid]
        self.cfg["custom_gestures"].append(entry)
        return True

    def match(self, mode: str, raw_points: np.ndarray, threshold: float = 0.22):
        norm = normalize_trajectory(raw_points, n=64)
        if norm is None:
            return None

        best_id = None
        best_dist = 1e9
        for g in self.cfg.get("custom_gestures", []):
            if g.get("type") != "dynamic_template":
                continue
            if g.get("mode") not in (mode, "both"):
                continue
            templ = np.array(g.get("template", []), dtype=np.float32)
            if templ.shape != (64, 2):
                continue
            d = template_distance(norm, templ)
            if d < best_dist:
                best_dist = d
                best_id = g.get("id")

        if best_id is not None and best_dist <= threshold:
            return best_id, best_dist
        return None
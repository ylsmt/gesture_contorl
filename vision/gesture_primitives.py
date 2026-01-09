import numpy as np

TIP = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
PIP = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}
MCP = {"thumb": 2, "index": 5, "middle": 9, "ring": 13, "pinky": 17}

def dist(a, b) -> float:
    return float(np.linalg.norm(a - b))

def palm_width(lm) -> float:
    # index_mcp=5, pinky_mcp=17
    return float(np.linalg.norm(lm[MCP["index"]] - lm[MCP["pinky"]])) + 1e-6

def is_extended_y(lm, tip_i, pip_i) -> bool:
    # y 更小更靠上
    return lm[tip_i, 1] < lm[pip_i, 1]

def finger_states(lm):
    """
    返回：thumb_ext, ext_index, ext_middle, ext_ring, ext_pinky
    thumb_ext 用 tip-mcp 相对掌宽估计，更鲁棒
    """
    ext_index = is_extended_y(lm, TIP["index"], PIP["index"])
    ext_middle = is_extended_y(lm, TIP["middle"], PIP["middle"])
    ext_ring = is_extended_y(lm, TIP["ring"], PIP["ring"])
    ext_pinky = is_extended_y(lm, TIP["pinky"], PIP["pinky"])

    pw = palm_width(lm)
    thumb_ext = dist(lm[TIP["thumb"]], lm[MCP["thumb"]]) / pw > 0.55
    return thumb_ext, ext_index, ext_middle, ext_ring, ext_pinky

def classify_static(lm, pinch_thr_ratio=0.33, close_thr_ratio=0.22):
    """
    返回静态手势ID或 None（None 表示未分类；外层可映射为 UNKNOWN）
    支持：
      OPEN_PALM / FIST / THUMBS_UP / V_SIGN / INDEX_ONLY / THUMB_PINKY / OK_SIGN
    """
    if lm is None:
        return None

    thumb_ext, ext_index, ext_middle, ext_ring, ext_pinky = finger_states(lm)
    n_other = sum([ext_index, ext_middle, ext_ring, ext_pinky])

    # OPEN_PALM：四指至少3伸出
    if n_other >= 3:
        return "OPEN_PALM"

    # FIST：四指都不伸出且拇指也不伸出（避免吞掉 THUMBS_UP）
    if n_other == 0 and (not thumb_ext):
        return "FIST"

    # THUMBS_UP：拇指伸出，四指都不伸出
    if thumb_ext and n_other == 0:
        return "THUMBS_UP"

    # V_SIGN：食指+中指伸出
    if ext_index and ext_middle and (not ext_ring) and (not ext_pinky):
        return "V_SIGN"

    # INDEX_ONLY：仅食指伸出
    if ext_index and (not ext_middle) and (not ext_ring) and (not ext_pinky):
        return "INDEX_ONLY"

    # THUMB_PINKY：拇指+小拇指
    if thumb_ext and ext_pinky and (not ext_index) and (not ext_middle) and (not ext_ring):
        return "THUMB_PINKY"

    # OK_SIGN：thumb_tip 与 index_tip 接近 + 其它至少两指伸出
    pw = palm_width(lm)
    pinch = dist(lm[TIP["thumb"]], lm[TIP["index"]]) / pw
    if pinch < pinch_thr_ratio and sum([ext_middle, ext_ring, ext_pinky]) >= 2:
        return "OK_SIGN"

    return None

def pinch_ratio(lm, tip_a, tip_b) -> float:
    pw = palm_width(lm)
    return dist(lm[tip_a], lm[tip_b]) / pw

def close_ratio(lm, tip_a, tip_b) -> float:
    pw = palm_width(lm)
    return dist(lm[tip_a], lm[tip_b]) / pw
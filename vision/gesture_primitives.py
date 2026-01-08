import numpy as np

def palm_width(lm):
    # index_mcp=5, pinky_mcp=17
    return float(np.linalg.norm(lm[5] - lm[17])) + 1e-6

def dist(a, b):
    return float(np.linalg.norm(a - b))

def is_extended_y(lm, tip, pip):
    # y小表示更靠上
    return lm[tip, 1] < lm[pip, 1]

def classify_open_palm_fist_v_ok_thumbs(lm, pinch_thr_ratio=0.33, close_thr_ratio=0.22):
    """
    返回: OPEN_PALM / FIST / V_SIGN / OK_SIGN / THUMBS_UP / None
    """
    if lm is None:
        return None
    pw = palm_width(lm)

    TIP = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
    PIP = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}

    ext_index = is_extended_y(lm, TIP["index"], PIP["index"])
    ext_middle = is_extended_y(lm, TIP["middle"], PIP["middle"])
    ext_ring = is_extended_y(lm, TIP["ring"], PIP["ring"])
    ext_pinky = is_extended_y(lm, TIP["pinky"], PIP["pinky"])

    # 拇指是否伸出：用 thumb_tip(4) 与 thumb_ip(3) 方向距离粗判
    thumb_open = dist(lm[4], lm[3]) / pw > 0.18

    n_other = sum([ext_index, ext_middle, ext_ring, ext_pinky])

    # 中立张开：>=3 指伸出
    if n_other >= 3:
        return "OPEN_PALM"

    # 握拳：四指都不伸出（拇指不强制）
    if n_other == 0 and not ext_index and not ext_middle and not ext_ring and not ext_pinky:
        return "FIST"

    # V：食+中伸出
    if ext_index and ext_middle and (not ext_ring) and (not ext_pinky):
        return "V_SIGN"

    # OK：thumb-tip 与 index-tip 接近 + 其余至少两指伸出
    pinch = dist(lm[4], lm[8]) / pw
    if pinch < pinch_thr_ratio and sum([ext_middle, ext_ring, ext_pinky]) >= 2:
        return "OK_SIGN"

    # THUMBS_UP：thumb_open=True 且其它四指都收拢
    if thumb_open and n_other == 0:
        return "THUMBS_UP"

    return None

def pinch_ratio(lm, a_tip, b_tip):
    pw = palm_width(lm)
    return dist(lm[a_tip], lm[b_tip]) / pw

def close_ratio(lm, tip_a, tip_b):
    pw = palm_width(lm)
    return dist(lm[tip_a], lm[tip_b]) / pw
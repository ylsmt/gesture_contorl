import numpy as np

TIP = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
PIP = {"index": 6, "middle": 10, "ring": 14, "pinky": 18}
MCP = {"thumb": 2, "index": 5, "middle": 9, "ring": 13, "pinky": 17}

def dist(a, b) -> float:
    return float(np.linalg.norm(a - b))

def palm_width(lm) -> float:
    return float(np.linalg.norm(lm[MCP["index"]] - lm[MCP["pinky"]])) + 1e-6

def palm_center(lm):
    return (lm[MCP["index"]] + lm[MCP["pinky"]] + lm[0]) / 3.0

def cos_sim(a, b) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-6 or nb < 1e-6:
        return -1.0
    return float(np.dot(a, b) / (na * nb))

def is_extended_y(lm, tip_i, pip_i) -> bool:
    return lm[tip_i, 1] < lm[pip_i, 1]

def is_finger_extended_dir(lm, mcp_i: int, tip_i: int, center, palm_w: float,
                           len_thr: float, cos_thr: float) -> bool:
    v = lm[tip_i] - lm[mcp_i]
    u = lm[tip_i] - center
    if (np.linalg.norm(v) / palm_w) <= float(len_thr):
        return False
    return cos_sim(v, u) >= float(cos_thr)

def _default_rules():
    return {
        "use_direction": True,
        "index": {"len_thr": 0.55, "cos_thr": 0.55},
        "middle": {"len_thr": 0.55, "cos_thr": 0.55},
        "ring": {"len_thr": 0.55, "cos_thr": 0.55},
        "pinky": {"len_thr": 0.50, "cos_thr": 0.50},
        "thumb": {"len_thr": 0.50, "cos_thr": 0.20},
        "single_finger_enhance": True,
        "others_fold_len_thr": 0.45
    }

def finger_states(lm, rules_cfg=None):
    """
    返回：thumb_ext, ext_index, ext_middle, ext_ring, ext_pinky, len_ratios(dict)
    len_ratios：每指 |tip-mcp| / palm_w，用于单指增强
    """
    rules = _default_rules()
    if isinstance(rules_cfg, dict):
        # 浅合并
        rules.update({k: v for k, v in rules_cfg.items() if k in rules})

    pw = palm_width(lm)
    c = palm_center(lm)

    # 每指长度比
    len_ratio = {
        "thumb": dist(lm[TIP["thumb"]], lm[MCP["thumb"]]) / pw,
        "index": dist(lm[TIP["index"]], lm[MCP["index"]]) / pw,
        "middle": dist(lm[TIP["middle"]], lm[MCP["middle"]]) / pw,
        "ring": dist(lm[TIP["ring"]], lm[MCP["ring"]]) / pw,
        "pinky": dist(lm[TIP["pinky"]], lm[MCP["pinky"]]) / pw,
    }

    use_dir = bool(rules.get("use_direction", True))

    if use_dir:
        ext_index = is_finger_extended_dir(lm, MCP["index"], TIP["index"], c, pw,
                                           rules["index"]["len_thr"], rules["index"]["cos_thr"])
        ext_middle = is_finger_extended_dir(lm, MCP["middle"], TIP["middle"], c, pw,
                                            rules["middle"]["len_thr"], rules["middle"]["cos_thr"])
        ext_ring = is_finger_extended_dir(lm, MCP["ring"], TIP["ring"], c, pw,
                                          rules["ring"]["len_thr"], rules["ring"]["cos_thr"])
        ext_pinky = is_finger_extended_dir(lm, MCP["pinky"], TIP["pinky"], c, pw,
                                           rules["pinky"]["len_thr"], rules["pinky"]["cos_thr"])
    else:
        # 回退：y 规则
        ext_index = is_extended_y(lm, TIP["index"], PIP["index"])
        ext_middle = is_extended_y(lm, TIP["middle"], PIP["middle"])
        ext_ring = is_extended_y(lm, TIP["ring"], PIP["ring"])
        ext_pinky = is_extended_y(lm, TIP["pinky"], PIP["pinky"])

    # 拇指：长度 + 方向（方向阈值较低）
    thumb_len_thr = float(rules["thumb"]["len_thr"])
    thumb_cos_thr = float(rules["thumb"]["cos_thr"])
    thumb_dir = cos_sim(lm[TIP["thumb"]] - lm[MCP["thumb"]], lm[TIP["thumb"]] - c)
    thumb_ext = (len_ratio["thumb"] > thumb_len_thr) and (thumb_dir > thumb_cos_thr)

    return thumb_ext, ext_index, ext_middle, ext_ring, ext_pinky, len_ratio

def classify_static(lm, pinch_thr_ratio=0.33, close_thr_ratio=0.22, rules_cfg=None):
    """
    返回静态手势ID或 None
    """
    if lm is None:
        return None

    thumb_ext, ext_index, ext_middle, ext_ring, ext_pinky, len_ratio = finger_states(lm, rules_cfg=rules_cfg)
    n_other = sum([ext_index, ext_middle, ext_ring, ext_pinky])

    # OPEN_PALM (严格化：5指伸展 + 手掌朝上)
    # 目的：作为隐式中立手势，普通张手不触发
    if n_other == 4 and thumb_ext:
        # 方向判定：手掌中心(c)应该在食指指尖(lm[8])的下方 (y坐标更大)
        # 且保证拇指充分伸展（len_ratio > 0.65，默认0.5可能太松）
        c = palm_center(lm)
        if lm[TIP["index"]][1] < c[1]:
            # 可选：进一步检查其他指尖是否也在掌心上方
            if lm[TIP["pinky"]][1] < c[1]:
                 return "OPEN_PALM"

    # FIST（更严格，避免吞掉 THUMBS_UP）
    if n_other == 0 and (not thumb_ext):
        return "FIST"

    # 单指增强：要求其它指明确收拢
    rules = _default_rules()
    if isinstance(rules_cfg, dict):
        rules.update({k: v for k, v in rules_cfg.items() if k in rules})
    enhance = bool(rules.get("single_finger_enhance", True))
    others_fold_thr = float(rules.get("others_fold_len_thr", 0.45))

    def others_fold(exclude: set) -> bool:
        # exclude: {"thumb"} / {"index"} / etc
        for k in ["thumb", "index", "middle", "ring", "pinky"]:
            if k in exclude:
                continue
            if len_ratio[k] >= others_fold_thr:
                return False
        return True

    # THUMBS_UP
    if thumb_ext and n_other == 0:
        if (not enhance) or others_fold({"thumb"}):
            return "THUMBS_UP"

    # V_SIGN
    if ext_index and ext_middle and (not ext_ring) and (not ext_pinky):
        return "V_SIGN"

    # INDEX_ONLY
    if ext_index and (not ext_middle) and (not ext_ring) and (not ext_pinky):
        if (not enhance) or others_fold({"index"}):
            return "INDEX_ONLY"

    # THUMB_PINKY
    if thumb_ext and ext_pinky and (not ext_index) and (not ext_middle) and (not ext_ring):
        if (not enhance) or others_fold({"thumb", "pinky"}):
            return "THUMB_PINKY"

    # OK_SIGN（thumb_tip 与 index_tip 接近 + 其它至少两指伸出）
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
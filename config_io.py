import json
import os
from copy import deepcopy

DEFAULT_CONFIG_PATH = os.path.join("config", "default_config.json")

DEFAULT_CONFIG = {
  "general": {
    "camera_index": 0,
    "camera_width": 640,
    "camera_height": 480,
    "camera_fps": 30,

    "mirror_camera": True,
    "show_camera_preview": True,
    "osd_enabled": True,

    "recognition_enabled": True,
    "execution_enabled": True,
    "mouse_move_output_enabled": True,

    "infer_scale": 0.6,
    "ui_fps": 24,
    "infer_fps": 12,

    "stable_frames": 3,
    "cooldown_ms": 450,

    "mouse_smoothing": 0.35,
    "mouse_sensitivity": 1.0,
    "mouse_deadzone_px": 2,

    "pinch_threshold_ratio": 0.33,
    "two_finger_close_ratio": 0.22,

    "scroll_gain": 1.6,
    "scroll_deadzone_px": 6,
    "scroll_max_step": 120
  },

  "gesture_catalog": [
    {
      "id": "OPEN_PALM",
      "title": "张开手掌",
      "type": "static",
      "mode": "bare",
      "description": "手掌张开（中立）",
      "default_use": "neutral",
      "notes": "默认中立手势，不绑定动作",
      "enable_when": {},
      "params": {}
    },
    {
      "id": "THUMBS_UP",
      "title": "竖大拇指",
      "type": "static",
      "mode": "bare",
      "description": "仅大拇指伸出，其余收拢",
      "default_use": "toggle_recognition",
      "notes": "启停识别功能",
      "enable_when": {},
      "params": {"stable_frames": 4, "cooldown_ms": 1200}
    },
    {
      "id": "V_SIGN",
      "title": "V手势",
      "type": "static",
      "mode": "bare",
      "description": "食指+中指伸出",
      "default_use": "mouse_move_mode",
      "notes": "默认作为鼠标移动模式启用条件（非绑定动作）",
      "enable_when": {},
      "params": {}
    },
    {
      "id": "PINCH_RIGHT_CLICK",
      "title": "拇指+中指捏合",
      "type": "composite",
      "mode": "bare",
      "description": "鼠标移动模式下，拇指与中指捏合触发",
      "default_use": "right_click",
      "notes": "",
      "enable_when": {"mouse_move_mode": True},
      "params": {"cooldown_ms": 500}
    },
    {
      "id": "INDEX_MIDDLE_DOUBLE_CLICK",
      "title": "食指+中指并拢",
      "type": "composite",
      "mode": "bare",
      "description": "鼠标移动模式下，食指与中指并拢触发双击",
      "default_use": "double_click_left",
      "notes": "",
      "enable_when": {"mouse_move_mode": True},
      "params": {"cooldown_ms": 700}
    },
    {
      "id": "PINCH_SCROLL",
      "title": "捏合滚动",
      "type": "state",
      "mode": "bare",
      "description": "拇指+食指捏合进入滚动模式，位移比例滚动",
      "default_use": "scroll_proportional",
      "notes": "纵向dy滚动；横向dx使用Shift+Wheel",
      "enable_when": {"mouse_move_mode": True},
      "params": {}
    },
    {
      "id": "SWIPE_LEFT",
      "title": "左挥",
      "type": "dynamic",
      "mode": "bare",
      "description": "轨迹向左挥动",
      "default_use": "custom_bind",
      "notes": "",
      "enable_when": {},
      "params": {}
    },
    {
      "id": "SWIPE_RIGHT",
      "title": "右挥",
      "type": "dynamic",
      "mode": "bare",
      "description": "轨迹向右挥动",
      "default_use": "custom_bind",
      "notes": "",
      "enable_when": {},
      "params": {}
    },
    {
      "id": "SWIPE_UP",
      "title": "上挥",
      "type": "dynamic",
      "mode": "bare",
      "description": "轨迹向上挥动",
      "default_use": "custom_bind",
      "notes": "",
      "enable_when": {},
      "params": {}
    },
    {
      "id": "SWIPE_DOWN",
      "title": "下挥",
      "type": "dynamic",
      "mode": "bare",
      "description": "轨迹向下挥动",
      "default_use": "custom_bind",
      "notes": "",
      "enable_when": {},
      "params": {}
    }
  ],

  "action_catalog": [
    {"type": "toggle_recognition", "description": "启停识别（推理开关）"},
    {"type": "toggle_execution", "description": "启停执行（识别继续，仅动作开关）"},
    {"type": "toggle_camera_preview", "description": "显示/隐藏摄像预览"},
    {"type": "toggle_mouse_move_output", "description": "启用/禁用鼠标移动输出（moveTo）"},
    {"type": "click_left", "description": "左键单击"},
    {"type": "double_click_left", "description": "左键双击"},
    {"type": "click_right", "description": "右键单击"},
    {"type": "mouse_down_left", "description": "左键按下"},
    {"type": "mouse_up_left", "description": "左键抬起"},
    {"type": "scroll_v", "description": "纵向滚动", "schema": {"amount": "int"}},
    {"type": "scroll_h_shiftwheel", "description": "横向滚动（Shift+Wheel）", "schema": {"amount": "int"}},
    {"type": "hotkey", "description": "组合键", "schema": {"keys": "list[str]"}},
    {"type": "key", "description": "按键", "schema": {"key": "str"}},
    {"type": "open_program", "description": "打开程序", "schema": {"path": "str"}},
    {"type": "shell", "description": "执行命令", "schema": {"cmd": "str"}}
  ],

  "bindings": {
    "global": {
      "THUMBS_UP": {"type": "toggle_recognition"},
      "SWIPE_LEFT": {"type": "hotkey", "keys": ["alt", "left"]},
      "SWIPE_RIGHT": {"type": "hotkey", "keys": ["alt", "right"]}
    },
    "per_app": {
      "POWERPNT.EXE": {
        "SWIPE_LEFT": {"type": "key", "key": "left"},
        "SWIPE_RIGHT": {"type": "key", "key": "right"}
      }
    }
  }
}

def deep_merge(dst: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            deep_merge(dst[k], v)
        else:
            dst[k] = v
    return dst

def load_config(path: str = DEFAULT_CONFIG_PATH) -> dict:
    cfg = deepcopy(DEFAULT_CONFIG)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
        deep_merge(cfg, user)
    return cfg

def save_config(cfg: dict, path: str = DEFAULT_CONFIG_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
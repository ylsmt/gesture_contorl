from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

Json = Union[dict, list, str, int, float, bool, None]

@dataclass
class ValidationError:
    path: str
    message: str

def _is_type(v: Any, t: str) -> bool:
    if t == "int":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "float":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "bool":
        return isinstance(v, bool)
    if t == "str":
        return isinstance(v, str)
    if t == "dict":
        return isinstance(v, dict)
    if t == "list":
        return isinstance(v, list)
    if t.startswith("list[") and t.endswith("]"):
        if not isinstance(v, list):
            return False
        inner = t[5:-1]
        return all(_is_type(x, inner) for x in v)
    return True  # unknown types: don't block

def validate_object(obj: dict, schema: dict, path="$") -> List[ValidationError]:
    """
    schema 约定：
      {
        "required": ["a","b"],
        "properties": {
           "a": {"type":"int"},
           "b": {"type":"list[str]"}
        },
        "additionalProperties": True/False
      }
    """
    errs: List[ValidationError] = []
    if not isinstance(obj, dict):
        return [ValidationError(path, "不是对象(dict)")]

    required = schema.get("required", [])
    props = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)

    for k in required:
        if k not in obj:
            errs.append(ValidationError(f"{path}.{k}", "缺少必填字段"))

    for k, v in obj.items():
        if k in props:
            spec = props[k]
            typ = spec.get("type")
            if typ and not _is_type(v, typ):
                errs.append(ValidationError(f"{path}.{k}", f"类型错误，应为 {typ}"))
        else:
            if additional is False:
                errs.append(ValidationError(f"{path}.{k}", "不允许的字段"))

    return errs

def action_schema_from_catalog(action_catalog: list, action_type: str) -> Optional[dict]:
    for it in action_catalog:
        if it.get("type") == action_type:
            # catalog 里 schema 是简写：{"amount":"int"}，这里转换成 validate_object 的格式
            simple = it.get("schema", {}) or {}
            props = {k: {"type": v} for k, v in simple.items()}
            required = list(simple.keys())  # 简化：schema里列出的都默认必填
            return {
                "required": required,
                "properties": props,
                "additionalProperties": False
            }
    return None

# enable_when 的统一 schema（可扩展）
ENABLE_WHEN_SCHEMA = {
    "required": [],
    "properties": {
        "mouse_move_mode": {"type": "bool"},
        "recognition_enabled": {"type": "bool"},
        "execution_enabled": {"type": "bool"},
        "mouse_move_output_enabled": {"type": "bool"},
        "camera_preview_enabled": {"type": "bool"}
    },
    "additionalProperties": False
}

# gesture params 的通用 schema（不强制，允许扩展字段）
GESTURE_PARAMS_SCHEMA = {
    "required": [],
    "properties": {
        "cooldown_ms": {"type": "int"},
        "stable_frames": {"type": "int"}
    },
    "additionalProperties": True
}
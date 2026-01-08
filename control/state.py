from dataclasses import dataclass

@dataclass
class SystemState:
    recognition_enabled: bool = True
    execution_enabled: bool = True
    camera_preview_enabled: bool = True
    mouse_move_output_enabled: bool = True

    mouse_move_mode: bool = False  # 由手势/条件驱动（例如 V_SIGN 保持为 True）
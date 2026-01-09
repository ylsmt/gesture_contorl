from dataclasses import dataclass

@dataclass
class SystemState:
    recognition_enabled: bool = True
    execution_enabled: bool = True

    # 预览仅影响UI显示
    camera_preview_enabled: bool = True

    # 摄像头设备是否开启（控制是否占用摄像头、是否有帧输入）
    camera_device_enabled: bool = True

    # 是否允许输出鼠标移动（moveTo）
    mouse_move_output_enabled: bool = True

    # 鼠标移动模式（用于移动输出），由手势/规则决定
    mouse_move_mode: bool = False
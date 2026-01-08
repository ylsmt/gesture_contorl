import subprocess
import pyautogui
from pynput.mouse import Controller as MouseController, Button

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

mouse = MouseController()

def do_action(action: dict, state):
    if not action:
        return

    t = action.get("type")

    # 开关类：永远允许执行（否则关了打不开）
    if t == "toggle_recognition":
        state.recognition_enabled = not state.recognition_enabled
        return
    if t == "toggle_execution":
        state.execution_enabled = not state.execution_enabled
        if not state.execution_enabled:
            # 避免拖拽卡住
            try:
                mouse.release(Button.left)
            except Exception:
                pass
        return
    if t == "toggle_camera_preview":
        state.camera_preview_enabled = not state.camera_preview_enabled
        return
    if t == "toggle_mouse_move_output":
        state.mouse_move_output_enabled = not state.mouse_move_output_enabled
        return

    # 其余动作：受 execution_enabled 门控（recognition 门控由上层处理）
    if not state.execution_enabled:
        return

    if t == "scroll_v":
        pyautogui.scroll(int(action.get("amount", 0)))
    elif t == "scroll_h_shiftwheel":
        amt = int(action.get("amount", 0))
        # Shift+Wheel 模拟横滚：按住 shift 再滚轮
        pyautogui.keyDown("shift")
        try:
            pyautogui.scroll(amt)
        finally:
            pyautogui.keyUp("shift")

    elif t == "key":
        key = action.get("key")
        if key:
            pyautogui.press(key)

    elif t == "hotkey":
        keys = action.get("keys", [])
        if keys:
            pyautogui.hotkey(*keys)

    elif t == "click_left":
        pyautogui.click(button="left")

    elif t == "double_click_left":
        pyautogui.doubleClick(button="left")

    elif t == "click_right":
        pyautogui.click(button="right")

    elif t == "mouse_down_left":
        mouse.press(Button.left)

    elif t == "mouse_up_left":
        mouse.release(Button.left)

    elif t == "open_program":
        path = action.get("path")
        if path:
            subprocess.Popen([path], shell=False)

    elif t == "shell":
        cmd = action.get("cmd")
        if cmd:
            subprocess.Popen(cmd, shell=True)
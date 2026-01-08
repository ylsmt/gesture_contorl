import platform

def get_foreground_process_name():
    if platform.system() != "Windows":
        return None
    try:
        import win32gui
        import win32process
        import psutil
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name()
    except Exception:
        return None
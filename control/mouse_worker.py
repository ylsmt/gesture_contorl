import time
import threading
from dataclasses import dataclass
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

@dataclass
class Target:
    x: float = 0.0
    y: float = 0.0
    valid: bool = False

class MouseMoveWorker:
    def __init__(self, hz=60):
        self.hz = max(10, int(hz))
        self._lock = threading.Lock()
        self._tgt = Target()
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def set_target(self, x, y):
        with self._lock:
            self._tgt = Target(float(x), float(y), True)

    def invalidate(self):
        with self._lock:
            self._tgt.valid = False

    def _run(self):
        interval = 1.0 / self.hz
        while self._running:
            t0 = time.time()
            with self._lock:
                tgt = Target(self._tgt.x, self._tgt.y, self._tgt.valid)
            if tgt.valid:
                try:
                    pyautogui.moveTo(tgt.x, tgt.y)
                except Exception:
                    pass
            dt = time.time() - t0
            sleep = interval - dt
            if sleep > 0:
                time.sleep(sleep)
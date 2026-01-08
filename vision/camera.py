import cv2
from PyQt6.QtCore import QThread, pyqtSignal

class CameraThread(QThread):
    frame_signal = pyqtSignal(object)

    def __init__(self, index=0, width=640, height=480, fps=30, mirror=True):
        super().__init__()
        self.index = int(index)
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.mirror = bool(mirror)
        self._running = True

    def stop(self):
        self._running = False

    def set_mirror(self, mirror: bool):
        self.mirror = bool(mirror)

    def run(self):
        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

        while self._running:
            ok, frame = cap.read()
            if not ok:
                continue
            if self.mirror:
                frame = cv2.flip(frame, 1)
            self.frame_signal.emit(frame)

        cap.release()
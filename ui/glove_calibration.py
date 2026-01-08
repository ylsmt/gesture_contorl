import cv2
import numpy as np
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt

def _to_pix(frame_bgr, target_w=760):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    scale = target_w / max(1, w)
    nh = int(h * scale)
    rgb = cv2.resize(rgb, (target_w, nh))
    h, w = rgb.shape[:2]
    qimg = QImage(rgb.data, w, h, w*3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimg)

class GloveCalibrationDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("手套HSV校准")
        self.resize(860, 640)

        self.lbl = QLabel("等待画面…")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl.setStyleSheet("background:#111; color:#bbb;")

        self.btn_sample = QPushButton("采样并更新阈值")
        self.btn_close = QPushButton("关闭")

        bottom = QHBoxLayout()
        bottom.addWidget(QLabel("提示：把手套放在画面中央框内，尽量填满框。"))
        bottom.addStretch(1)
        bottom.addWidget(self.btn_sample)
        bottom.addWidget(self.btn_close)

        lay = QVBoxLayout()
        lay.addWidget(self.lbl)
        lay.addLayout(bottom)
        self.setLayout(lay)

        self.last_frame = None
        self.btn_sample.clicked.connect(self.sample)
        self.btn_close.clicked.connect(self.accept)

    def update_frame(self, frame_bgr):
        self.last_frame = frame_bgr.copy()
        vis = frame_bgr.copy()
        h, w = vis.shape[:2]
        rw, rh = int(w*0.35), int(h*0.35)
        x0, y0 = (w-rw)//2, (h-rh)//2
        cv2.rectangle(vis, (x0,y0), (x0+rw, y0+rh), (0,255,255), 2)
        self.lbl.setPixmap(_to_pix(vis))

    def sample(self):
        if self.last_frame is None:
            return
        frame = self.last_frame
        h, w = frame.shape[:2]
        rw, rh = int(w*0.35), int(h*0.35)
        x0, y0 = (w-rw)//2, (h-rh)//2
        roi = frame[y0:y0+rh, x0:x0+rw]

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = (hsv[...,2] > 40) & (hsv[...,1] > 40)
        pix = hsv[mask]
        if pix.shape[0] < 500:
            QMessageBox.warning(self, "采样失败", "有效像素太少，请调整手套位置或光照")
            return

        lower = np.percentile(pix, 5, axis=0)
        upper = np.percentile(pix, 95, axis=0)

        lower = np.clip(lower - np.array([5,30,30]), 0, 255).astype(int)
        upper = np.clip(upper + np.array([5,30,30]), 0, 255).astype(int)

        self.cfg.setdefault("glove", {})
        self.cfg["glove"]["hsv_lower"] = lower.tolist()
        self.cfg["glove"]["hsv_upper"] = upper.tolist()

        QMessageBox.information(self, "校准完成",
                                f"已更新 HSV\nlower={self.cfg['glove']['hsv_lower']}\nupper={self.cfg['glove']['hsv_upper']}")
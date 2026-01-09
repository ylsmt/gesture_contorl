import numpy as np
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox

class CustomGestureRecorder(QDialog):
    """
    由 MainWindow 驱动：开始录制时不断 append 点；停止时保存。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("录制自定义动态手势")
        self.resize(520, 180)

        self.name_in = QLineEdit()
        self.name_in.setPlaceholderText("手势ID（例如 MY_CIRCLE）")

        self.lbl = QLabel("点击开始后做一次完整轨迹，再点停止。")
        self.btn_start = QPushButton("开始录制")
        self.btn_stop = QPushButton("停止并保存")
        self.btn_stop.setEnabled(False)

        lay = QVBoxLayout()
        lay.addWidget(self.lbl)

        row = QHBoxLayout()
        row.addWidget(QLabel("ID:"))
        row.addWidget(self.name_in, 2)
        lay.addLayout(row)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_start)
        btns.addWidget(self.btn_stop)
        lay.addLayout(btns)
        self.setLayout(lay)

        self.recording = False
        self.points = []

        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)

    def start(self):
        gid = self.name_in.text().strip()
        if not gid:
            QMessageBox.warning(self, "提示", "请先填写手势ID")
            return
        self.recording = True
        self.points = []
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl.setText("录制中… 请做动作轨迹")

    def add_point(self, x, y):
        if self.recording:
            self.points.append((float(x), float(y)))

    def stop(self):
        self.recording = False
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl.setText("已停止。")
        if len(self.points) < 12:
            QMessageBox.warning(self, "失败", "轨迹太短，请重录")
            return
        self.accept()

    def get_result(self):
        gid = self.name_in.text().strip()
        pts = np.array(self.points, dtype=np.float32)
        return gid, pts
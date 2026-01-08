from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer

class OSD(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.label = QLabel("")
        self.label.setStyleSheet("""
            QLabel{
                color:#fff;
                background-color: rgba(0,0,0,170);
                padding:10px 12px;
                border-radius:8px;
                font-size:14px;
            }
        """)
        lay = QVBoxLayout()
        lay.addWidget(self.label)
        self.setLayout(lay)

        self.timer = QTimer()
        self.timer.timeout.connect(self.hide)

    def show_message(self, text: str, ms=900):
        self.label.setText(text)
        self.adjustSize()
        self.move(20, 20)
        self.show()
        self.raise_()
        self.timer.stop()
        self.timer.start(ms)
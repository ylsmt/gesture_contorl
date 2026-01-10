from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt

class DebugOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.label = QLabel("")
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setStyleSheet("""
            QLabel{
                color:#00ff9a;
                background-color: rgba(0,0,0,170);
                padding:10px 12px;
                border-radius:8px;
                font-size:12px;
                font-family: Consolas, 'Microsoft YaHei', monospace;
            }
        """)

        lay = QVBoxLayout()
        lay.addWidget(self.label)
        self.setLayout(lay)

    def update_text(self, text: str):
        self.label.setText(text)
        self.adjustSize()
        # 右上角
        screen = self.screen().availableGeometry()
        x = screen.right() - self.width() - 20
        y = screen.top() + 20
        self.move(x, y)
        self.show()
        self.raise_()
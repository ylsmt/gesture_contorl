import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout
)

class ActionCatalogViewer(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("动作字典（Action Catalog）")
        self.resize(900, 520)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["type", "description", "schema(JSON)"])
        self.table.horizontalHeader().setStretchLastSection(True)

        self.btn_reload = QPushButton("刷新")
        self.btn_close = QPushButton("关闭")

        top = QHBoxLayout()
        top.addWidget(self.btn_reload)
        top.addStretch(1)
        top.addWidget(self.btn_close)

        lay = QVBoxLayout()
        lay.addLayout(top)
        lay.addWidget(self.table)
        self.setLayout(lay)

        self.btn_reload.clicked.connect(self.reload)
        self.btn_close.clicked.connect(self.accept)

        self.reload()

    def reload(self):
        self.table.setRowCount(0)
        cat = self.cfg.get("action_catalog", [])
        for it in cat:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(it.get("type", ""))))
            self.table.setItem(r, 1, QTableWidgetItem(str(it.get("description", ""))))
            self.table.setItem(r, 2, QTableWidgetItem(json.dumps(it.get("schema", {}), ensure_ascii=False)))
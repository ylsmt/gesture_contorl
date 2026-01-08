import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QMessageBox, QComboBox, QLineEdit, QTextEdit
)

GESTURE_TYPES = ["static", "dynamic", "composite", "state"]
GESTURE_MODES = ["bare", "glove", "both"]

class GestureCatalogEditor(QDialog):
    """
    编辑 cfg["gesture_catalog"] 列表。
    每条手势项：id/title/type/mode/description/default_use/notes/enable_when/params
    """
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("手势字典（Gesture Catalog）")
        self.resize(1100, 620)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "id", "title", "type", "mode", "default_use", "enable_when(JSON)", "params(JSON)"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)

        # 编辑区
        self.id_in = QLineEdit()
        self.title_in = QLineEdit()
        self.type_in = QComboBox(); self.type_in.addItems(GESTURE_TYPES)
        self.mode_in = QComboBox(); self.mode_in.addItems(GESTURE_MODES)
        self.default_use_in = QLineEdit()
        self.desc_in = QTextEdit(); self.desc_in.setPlaceholderText("description")
        self.notes_in = QTextEdit(); self.notes_in.setPlaceholderText("notes")
        self.enable_in = QTextEdit(); self.enable_in.setPlaceholderText('{"mouse_move_mode": true}')
        self.params_in = QTextEdit(); self.params_in.setPlaceholderText('{"cooldown_ms": 500, "stable_frames": 3}')

        self.btn_add = QPushButton("新增/更新")
        self.btn_del = QPushButton("删除选中")
        self.btn_reload = QPushButton("刷新")
        self.btn_close = QPushButton("关闭")

        top = QHBoxLayout()
        top.addWidget(self.btn_reload)
        top.addWidget(self.btn_del)
        top.addStretch(1)
        top.addWidget(self.btn_close)

        form1 = QHBoxLayout()
        form1.addWidget(QLabel("id"))
        form1.addWidget(self.id_in, 2)
        form1.addWidget(QLabel("title"))
        form1.addWidget(self.title_in, 2)
        form1.addWidget(QLabel("type"))
        form1.addWidget(self.type_in, 1)
        form1.addWidget(QLabel("mode"))
        form1.addWidget(self.mode_in, 1)
        form1.addWidget(QLabel("default_use"))
        form1.addWidget(self.default_use_in, 2)
        form1.addWidget(self.btn_add, 1)

        form2 = QHBoxLayout()
        form2.addWidget(QLabel("description"))
        form2.addWidget(self.desc_in, 3)
        form2.addWidget(QLabel("notes"))
        form2.addWidget(self.notes_in, 3)

        form3 = QHBoxLayout()
        form3.addWidget(QLabel("enable_when(JSON)"))
        form3.addWidget(self.enable_in, 3)
        form3.addWidget(QLabel("params(JSON)"))
        form3.addWidget(self.params_in, 3)

        lay = QVBoxLayout()
        lay.addLayout(top)
        lay.addWidget(self.table)
        lay.addLayout(form1)
        lay.addLayout(form2)
        lay.addLayout(form3)
        self.setLayout(lay)

        self.btn_reload.clicked.connect(self.reload)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_add.clicked.connect(self.add_or_update)
        self.btn_close.clicked.connect(self.accept)

        self.table.cellClicked.connect(self.on_row_clicked)

        self.reload()

    def _catalog(self):
        self.cfg.setdefault("gesture_catalog", [])
        return self.cfg["gesture_catalog"]

    def reload(self):
        cat = self._catalog()
        self.table.setRowCount(0)
        for it in cat:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(it.get("id", ""))))
            self.table.setItem(r, 1, QTableWidgetItem(str(it.get("title", ""))))
            self.table.setItem(r, 2, QTableWidgetItem(str(it.get("type", ""))))
            self.table.setItem(r, 3, QTableWidgetItem(str(it.get("mode", ""))))
            self.table.setItem(r, 4, QTableWidgetItem(str(it.get("default_use", ""))))
            self.table.setItem(r, 5, QTableWidgetItem(json.dumps(it.get("enable_when", {}), ensure_ascii=False)))
            self.table.setItem(r, 6, QTableWidgetItem(json.dumps(it.get("params", {}), ensure_ascii=False)))

    def on_row_clicked(self, row, col):
        cat = self._catalog()
        if row < 0 or row >= len(cat):
            return
        it = cat[row]
        self.id_in.setText(it.get("id", ""))
        self.title_in.setText(it.get("title", ""))
        self.type_in.setCurrentText(it.get("type", "static"))
        self.mode_in.setCurrentText(it.get("mode", "bare"))
        self.default_use_in.setText(it.get("default_use", ""))
        self.desc_in.setPlainText(it.get("description", ""))
        self.notes_in.setPlainText(it.get("notes", ""))
        self.enable_in.setPlainText(json.dumps(it.get("enable_when", {}), ensure_ascii=False, indent=2))
        self.params_in.setPlainText(json.dumps(it.get("params", {}), ensure_ascii=False, indent=2))

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        cat = self._catalog()
        if row >= len(cat):
            return
        del cat[row]
        self.reload()

    def add_or_update(self):
        gid = self.id_in.text().strip()
        if not gid:
            QMessageBox.warning(self, "提示", "id 不能为空")
            return

        try:
            enable_when = json.loads(self.enable_in.toPlainText().strip() or "{}")
            params = json.loads(self.params_in.toPlainText().strip() or "{}")
        except Exception as ex:
            QMessageBox.critical(self, "JSON错误", str(ex))
            return

        it = {
            "id": gid,
            "title": self.title_in.text().strip(),
            "type": self.type_in.currentText(),
            "mode": self.mode_in.currentText(),
            "description": self.desc_in.toPlainText().strip(),
            "default_use": self.default_use_in.text().strip(),
            "notes": self.notes_in.toPlainText().strip(),
            "enable_when": enable_when,
            "params": params
        }

        cat = self._catalog()
        # 同 id 覆盖
        found = False
        for i in range(len(cat)):
            if cat[i].get("id") == gid:
                cat[i] = it
                found = True
                break
        if not found:
            cat.append(it)

        self.reload()
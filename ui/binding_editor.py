from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QMessageBox, QInputDialog
)
import json

class BindingEditor(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("绑定编辑器")
        self.resize(920, 520)

        self.scope = QComboBox()
        self.scope.addItems(["global", "per_app"])
        self.app_name = QLineEdit()
        self.app_name.setPlaceholderText("进程名（scope=per_app 时有效，例如 POWERPNT.EXE）")

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["gesture_id", "action(JSON)"])
        self.table.horizontalHeader().setStretchLastSection(True)

        self.gesture_in = QLineEdit()
        self.gesture_in.setPlaceholderText("例如 THUMBS_UP / SWIPE_LEFT / PINCH_RIGHT_CLICK ...")
        self.action_in = QLineEdit()
        self.action_in.setPlaceholderText('例如 {"type":"toggle_execution"} 或 {"type":"hotkey","keys":["ctrl","l"]}')

        self.btn_add = QPushButton("添加/更新")
        self.btn_del = QPushButton("删除选中")
        self.btn_reload = QPushButton("刷新")
        self.btn_close = QPushButton("关闭")

        top = QHBoxLayout()
        top.addWidget(QLabel("范围："))
        top.addWidget(self.scope)
        top.addWidget(QLabel("应用："))
        top.addWidget(self.app_name, 2)
        top.addStretch(1)
        top.addWidget(self.btn_reload)

        form = QHBoxLayout()
        form.addWidget(self.gesture_in, 2)
        form.addWidget(self.action_in, 6)
        form.addWidget(self.btn_add)

        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_del)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_close)

        lay = QVBoxLayout()
        lay.addLayout(top)
        lay.addLayout(form)
        lay.addWidget(self.table)
        lay.addLayout(bottom)
        self.setLayout(lay)

        self.btn_reload.clicked.connect(self.reload)
        self.btn_add.clicked.connect(self.add_update)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_close.clicked.connect(self.accept)

        self.reload()

    def _map(self):
        b = self.cfg.setdefault("bindings", {})
        scope = self.scope.currentText()
        if scope == "global":
            return b.setdefault("global", {})
        else:
            app = self.app_name.text().strip()
            if not app:
                app, ok = QInputDialog.getText(self, "输入进程名", "进程名：")
                if not ok or not app.strip():
                    return {}
                self.app_name.setText(app.strip())
            per = b.setdefault("per_app", {})
            per.setdefault(app, {})
            return per[app]

    def reload(self):
        m = self._map()
        self.table.setRowCount(0)
        for k, v in m.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(k)))
            self.table.setItem(r, 1, QTableWidgetItem(json.dumps(v, ensure_ascii=False)))

    def add_update(self):
        gid = self.gesture_in.text().strip()
        if not gid:
            return
        try:
            action = json.loads(self.action_in.text().strip())
        except Exception as ex:
            QMessageBox.critical(self, "JSON错误", str(ex))
            return
        m = self._map()
        if m is not None:
            m[gid] = action
        self.reload()

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        gid = self.table.item(row, 0).text()
        m = self._map()
        if gid in m:
            del m[gid]
        self.reload()
import json
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QMessageBox, QInputDialog
)
from config.schema_runtime import action_schema_from_catalog, validate_object
from ui.forms import DynamicForm

class BindingEditor(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("绑定编辑器（表单模式）")
        self.resize(980, 620)

        self.scope = QComboBox()
        self.scope.addItems(["global", "per_app"])
        self.app_name = QLineEdit()
        self.app_name.setPlaceholderText("进程名（scope=per_app 时有效，例如 POWERPNT.EXE）")

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["gesture_id", "action"])
        self.table.horizontalHeader().setStretchLastSection(True)

        self.gesture_in = QLineEdit()
        self.gesture_in.setPlaceholderText("gesture_id，例如 THUMBS_UP / PINCH_RIGHT_CLICK / SWIPE_LEFT ...")

        self.action_type = QComboBox()
        self.action_type.addItems([it.get("type","") for it in self.cfg.get("action_catalog", []) if it.get("type")])

        self.btn_json = QPushButton("高级JSON…")
        self.btn_add = QPushButton("添加/更新")
        self.btn_del = QPushButton("删除选中")
        self.btn_reload = QPushButton("刷新")
        self.btn_close = QPushButton("关闭")

        self.form_holder = QVBoxLayout()
        self.form_widget = None
        self._rebuild_form({})

        top = QHBoxLayout()
        top.addWidget(QLabel("范围："))
        top.addWidget(self.scope)
        top.addWidget(QLabel("应用："))
        top.addWidget(self.app_name, 2)
        top.addStretch(1)
        top.addWidget(self.btn_reload)

        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("手势："))
        form_row.addWidget(self.gesture_in, 3)
        form_row.addWidget(QLabel("动作："))
        form_row.addWidget(self.action_type, 2)
        form_row.addWidget(self.btn_json)
        form_row.addWidget(self.btn_add)

        bottom = QHBoxLayout()
        bottom.addWidget(self.btn_del)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_close)

        lay = QVBoxLayout()
        lay.addLayout(top)
        lay.addWidget(self.table, 3)
        lay.addLayout(form_row)
        lay.addLayout(self.form_holder)
        lay.addLayout(bottom)
        self.setLayout(lay)

        self.btn_reload.clicked.connect(self.reload)
        self.btn_add.clicked.connect(self.add_update)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_close.clicked.connect(self.accept)
        self.btn_json.clicked.connect(self.edit_json)
        self.action_type.currentTextChanged.connect(self.on_action_type_changed)
        self.table.cellClicked.connect(self.on_row_clicked)

        self.reload()

    def _map(self):
        b = self.cfg.setdefault("bindings", {})
        scope = self.scope.currentText()
        if scope == "global":
            return b.setdefault("global", {})
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

    def _rebuild_form(self, initial: dict):
        # 清空 holder
        while self.form_holder.count():
            item = self.form_holder.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        atype = self.action_type.currentText().strip()
        it = next((x for x in self.cfg.get("action_catalog", []) if x.get("type") == atype), None)
        schema_simple = (it or {}).get("schema", {}) or {}
        self.form_widget = DynamicForm(schema_simple, initial=initial)
        self.form_holder.addWidget(self.form_widget)

    def on_action_type_changed(self, _):
        self._rebuild_form({})

    def on_row_clicked(self, row, col):
        m = self._map()
        if row < 0:
            return
        gid = self.table.item(row, 0).text()
        action = m.get(gid)
        if not isinstance(action, dict):
            return
        self.gesture_in.setText(gid)
        atype = action.get("type", "")
        if atype:
            self.action_type.setCurrentText(atype)
            # 重新建表单并填充
            init = {k: v for k, v in action.items() if k != "type"}
            self._rebuild_form(init)

    def edit_json(self):
        # 从表单生成 action 作为初值
        atype = self.action_type.currentText().strip()
        payload = self.form_widget.get_data() if self.form_widget else {}
        action = {"type": atype, **payload}
        text = json.dumps(action, ensure_ascii=False, indent=2)

        from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("编辑 action JSON（高级）")
        dlg.resize(640, 420)
        te = QTextEdit()
        te.setPlainText(text)
        ok = QPushButton("应用")
        cancel = QPushButton("取消")
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay = QVBoxLayout()
        lay.addWidget(te)
        lay.addLayout(row)
        dlg.setLayout(lay)

        def apply():
            try:
                obj = json.loads(te.toPlainText())
                if not isinstance(obj, dict) or "type" not in obj:
                    raise ValueError("action 必须为对象且包含 type")
                self.action_type.setCurrentText(obj["type"])
                init = {k: v for k, v in obj.items() if k != "type"}
                self._rebuild_form(init)
                dlg.accept()
            except Exception as ex:
                QMessageBox.critical(self, "JSON错误", str(ex))

        ok.clicked.connect(apply)
        cancel.clicked.connect(dlg.reject)
        dlg.exec()

    def add_update(self):
        gid = self.gesture_in.text().strip()
        if not gid:
            QMessageBox.warning(self, "提示", "gesture_id 不能为空")
            return

        atype = self.action_type.currentText().strip()
        payload = self.form_widget.get_data() if self.form_widget else {}
        action = {"type": atype, **payload}

        # schema 校验
        schema = action_schema_from_catalog(self.cfg.get("action_catalog", []), atype)
        if schema:
            errs = validate_object(payload, schema, path="$")
            if errs:
                msg = "\n".join([f"{e.path}: {e.message}" for e in errs])
                QMessageBox.critical(self, "参数校验失败", msg)
                return

        m = self._map()
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
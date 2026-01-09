import json
from typing import Any, Dict, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QMessageBox
)

from config.schema_runtime import action_schema_from_catalog, validate_object
from ui.forms import DynamicForm


class BindingEditor(QDialog):
    """
    固定编辑一个 scope：
      - scope="global": cfg["bindings"]["global"]
      - scope="per_app": cfg["bindings"]["per_app"][app_name]
    手势：下拉可输入
    动作：下拉 + schema 表单生成 + 校验 + 高级JSON
    """
    def __init__(self, cfg: dict, scope: str, app_name: Optional[str], parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.scope = scope
        self.app_name = app_name

        title = "绑定编辑 - 全局" if scope == "global" else f"绑定编辑 - {app_name}"
        self.setWindowTitle(title)
        self.resize(1040, 640)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["gesture_id", "action"])
        self.table.horizontalHeader().setStretchLastSection(True)

        # 手势输入：下拉 + 可输入
        self.gesture_in = QComboBox()
        self.gesture_in.setEditable(True)
        self._reload_gesture_choices()

        # 动作类型下拉（来自 action_catalog）
        self.action_type = QComboBox()
        self.action_type.addItems([it.get("type","") for it in self.cfg.get("action_catalog", []) if it.get("type")])

        self.btn_json = QPushButton("高级JSON…")
        self.btn_add = QPushButton("添加/更新")
        self.btn_del = QPushButton("删除选中")
        self.btn_reload = QPushButton("刷新")
        self.btn_close = QPushButton("关闭")

        # 表单区域
        self.form_holder = QVBoxLayout()
        self.form_widget: Optional[DynamicForm] = None
        self._rebuild_form(initial={})

        top = QHBoxLayout()
        top.addWidget(self.btn_reload)
        top.addWidget(self.btn_del)
        top.addStretch(1)
        top.addWidget(self.btn_close)

        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("手势："))
        form_row.addWidget(self.gesture_in, 2)
        form_row.addWidget(QLabel("动作："))
        form_row.addWidget(self.action_type, 2)
        form_row.addWidget(self.btn_json)
        form_row.addWidget(self.btn_add)

        lay = QVBoxLayout()
        lay.addLayout(top)
        lay.addWidget(self.table, 3)
        lay.addLayout(form_row)
        lay.addLayout(self.form_holder)
        self.setLayout(lay)

        # events
        self.btn_reload.clicked.connect(self.reload)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_add.clicked.connect(self.add_update)
        self.btn_close.clicked.connect(self.accept)
        self.btn_json.clicked.connect(self.edit_json)
        self.action_type.currentTextChanged.connect(self.on_action_type_changed)
        self.table.cellClicked.connect(self.on_row_clicked)

        self.reload()

    def _reload_gesture_choices(self):
        ids = []
        for it in self.cfg.get("gesture_catalog", []):
            gid = it.get("id")
            if gid:
                ids.append(gid)
        for it in self.cfg.get("custom_gestures", []):
            gid = it.get("id")
            if gid:
                ids.append(gid)
        ids = sorted(set(ids))
        self.gesture_in.clear()
        self.gesture_in.addItems(ids)

    def _map(self) -> dict:
        b = self.cfg.setdefault("bindings", {})
        if self.scope == "global":
            return b.setdefault("global", {})
        per = b.setdefault("per_app", {})
        per.setdefault(self.app_name, {})
        return per[self.app_name]

    def reload(self):
        self._reload_gesture_choices()
        m = self._map()
        self.table.setRowCount(0)
        for gid, action in m.items():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(gid)))
            self.table.setItem(r, 1, QTableWidgetItem(json.dumps(action, ensure_ascii=False)))

    def _rebuild_form(self, initial: Dict[str, Any]):
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
        self._rebuild_form(initial={})

    def on_row_clicked(self, row, col):
        m = self._map()
        gid = self.table.item(row, 0).text()
        action = m.get(gid)
        if not isinstance(action, dict):
            return

        self.gesture_in.setCurrentText(gid)
        atype = action.get("type", "")
        if atype:
            self.action_type.setCurrentText(atype)
            init = {k: v for k, v in action.items() if k != "type"}
            self._rebuild_form(initial=init)

    def edit_json(self):
        atype = self.action_type.currentText().strip()
        payload = self.form_widget.get_data() if self.form_widget else {}
        action = {"type": atype, **payload}
        text = json.dumps(action, ensure_ascii=False, indent=2)

        from PyQt6.QtWidgets import QDialog, QTextEdit, QVBoxLayout
        dlg = QDialog(self)
        dlg.setWindowTitle("编辑 action JSON（高级）")
        dlg.resize(680, 460)
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
                self._rebuild_form(initial=init)
                dlg.accept()
            except Exception as ex:
                QMessageBox.critical(self, "JSON错误", str(ex))

        ok.clicked.connect(apply)
        cancel.clicked.connect(dlg.reject)
        dlg.exec()

    def add_update(self):
        gid = self.gesture_in.currentText().strip()
        if not gid:
            QMessageBox.warning(self, "提示", "gesture_id 不能为空")
            return

        atype = self.action_type.currentText().strip()
        payload = self.form_widget.get_data() if self.form_widget else {}
        action = {"type": atype, **payload}

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
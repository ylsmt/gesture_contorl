from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QLabel, QInputDialog, QMessageBox
)
from ui.binding_editor import BindingEditor

class BindingManager(QDialog):
    """
    左侧：Global + per_app 已设置的应用列表
    点击后进入 BindingEditor（固定 scope / app）
    """
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("绑定管理")
        self.resize(720, 480)

        self.listw = QListWidget()
        self.btn_add_app = QPushButton("新增应用…")
        self.btn_del_app = QPushButton("删除应用")
        self.btn_edit = QPushButton("编辑…")
        self.btn_close = QPushButton("关闭")

        right = QVBoxLayout()
        right.addWidget(QLabel("操作"))
        right.addWidget(self.btn_edit)
        right.addSpacing(10)
        right.addWidget(self.btn_add_app)
        right.addWidget(self.btn_del_app)
        right.addStretch(1)
        right.addWidget(self.btn_close)

        row = QHBoxLayout()
        row.addWidget(self.listw, 3)
        row.addLayout(right, 1)

        lay = QVBoxLayout()
        lay.addLayout(row)
        self.setLayout(lay)

        self.btn_close.clicked.connect(self.accept)
        self.btn_add_app.clicked.connect(self.add_app)
        self.btn_del_app.clicked.connect(self.del_app)
        self.btn_edit.clicked.connect(self.edit_selected)
        self.listw.itemDoubleClicked.connect(lambda _: self.edit_selected())

        self.reload()

    def _per_app(self) -> dict:
        b = self.cfg.setdefault("bindings", {})
        return b.setdefault("per_app", {})

    def reload(self):
        self.listw.clear()
        self.listw.addItem("GLOBAL")
        for app in sorted(self._per_app().keys()):
            self.listw.addItem(app)

    def selected_key(self):
        it = self.listw.currentItem()
        if not it:
            return None
        return it.text()

    def add_app(self):
        app, ok = QInputDialog.getText(self, "新增应用", "输入进程名（例如 chrome.exe / POWERPNT.EXE）：")
        if not ok or not app.strip():
            return
        app = app.strip()
        per = self._per_app()
        if app not in per:
            per[app] = {}
        self.reload()

    def del_app(self):
        key = self.selected_key()
        if not key or key == "GLOBAL":
            return
        per = self._per_app()
        if key in per:
            del per[key]
        self.reload()

    def edit_selected(self):
        key = self.selected_key()
        if not key:
            return
        if key == "GLOBAL":
            dlg = BindingEditor(self.cfg, scope="global", app_name=None, parent=self)
        else:
            dlg = BindingEditor(self.cfg, scope="per_app", app_name=key, parent=self)
        dlg.exec()
from __future__ import annotations
from typing import Any, Dict, Optional

from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox
)

class DynamicForm(QWidget):
    """
    根据简化 schema {"amount":"int", "keys":"list[str]"} 生成输入控件。
    目前支持：int/float/bool/str/list[str]
    list[str] 用逗号分隔输入。
    """
    def __init__(self, schema_simple: Dict[str, str], initial: Optional[dict] = None, parent=None):
        super().__init__(parent)
        self.schema = schema_simple or {}
        self.widgets: Dict[str, QWidget] = {}
        self.layout = QFormLayout()
        self.setLayout(self.layout)

        initial = initial or {}
        for k, t in self.schema.items():
            w = self._make_widget(t, initial.get(k))
            self.widgets[k] = w
            self.layout.addRow(k, w)

    def _make_widget(self, t: str, v: Any) -> QWidget:
        if t == "int":
            w = QSpinBox()
            w.setRange(-10**9, 10**9)
            if isinstance(v, int):
                w.setValue(v)
            return w
        if t == "float":
            w = QDoubleSpinBox()
            w.setRange(-1e9, 1e9)
            w.setDecimals(3)
            if isinstance(v, (int, float)):
                w.setValue(float(v))
            return w
        if t == "bool":
            w = QCheckBox()
            w.setChecked(bool(v))
            return w
        if t == "list[str]":
            w = QLineEdit()
            if isinstance(v, list):
                w.setText(",".join(str(x) for x in v))
            return w
        # default str
        w = QLineEdit()
        if v is not None:
            w.setText(str(v))
        return w

    def get_data(self) -> dict:
        out = {}
        for k, t in self.schema.items():
            w = self.widgets[k]
            if t == "int":
                out[k] = int(w.value())  # type: ignore
            elif t == "float":
                out[k] = float(w.value())  # type: ignore
            elif t == "bool":
                out[k] = bool(w.isChecked())  # type: ignore
            elif t == "list[str]":
                text = w.text().strip()  # type: ignore
                out[k] = [s.strip() for s in text.split(",") if s.strip()]
            else:
                out[k] = w.text()  # type: ignore
        return out
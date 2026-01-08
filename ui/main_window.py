import time
import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QVBoxLayout, QHBoxLayout,
    QCheckBox, QMessageBox, QFileDialog, QDoubleSpinBox, QSpinBox
)
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import Qt, QTimer

from config_io import load_config, save_config, DEFAULT_CONFIG_PATH
from control.state import SystemState
from control.dispatcher import Dispatcher
from control.mouse_controller import MouseController, MouseParams
from control.mouse_worker import MouseMoveWorker

from ui.osd import OSD
from ui.binding_editor import BindingEditor

from vision.camera import CameraThread
from vision.bare_mediapipe import BareHandTracker
from vision.gesture_engine import GestureEngine

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("手势控制中心（MVP）")
        self.resize(1100, 760)

        self.cfg = load_config(DEFAULT_CONFIG_PATH)
        g = self.cfg["general"]

        # State
        self.state = SystemState(
            recognition_enabled=bool(g.get("recognition_enabled", True)),
            execution_enabled=bool(g.get("execution_enabled", True)),
            camera_preview_enabled=bool(g.get("show_camera_preview", True)),
            mouse_move_output_enabled=bool(g.get("mouse_move_output_enabled", True))
        )

        # UI
        self.preview = QLabel("预览")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background:#111; color:#bbb;")
        self.preview.setMinimumHeight(500)

        self.mode_box = QComboBox()
        self.mode_box.addItems(["bare"])  # MVP 先裸手，后续加 glove
        self.preview_toggle = QCheckBox("显示摄像")
        self.preview_toggle.setChecked(self.state.camera_preview_enabled)
        self.mirror_toggle = QCheckBox("镜像")
        self.mirror_toggle.setChecked(bool(g.get("mirror_camera", True)))
        self.osd_toggle = QCheckBox("OSD")
        self.osd_toggle.setChecked(bool(g.get("osd_enabled", True)))

        self.recog_toggle = QCheckBox("识别 ON")
        self.recog_toggle.setChecked(self.state.recognition_enabled)
        self.exec_toggle = QCheckBox("执行 ON")
        self.exec_toggle.setChecked(self.state.execution_enabled)
        self.mouse_move_output_toggle = QCheckBox("鼠标移动输出 ON")
        self.mouse_move_output_toggle.setChecked(self.state.mouse_move_output_enabled)

        self.spin_smooth = QDoubleSpinBox()
        self.spin_smooth.setRange(0.0, 0.95)
        self.spin_smooth.setSingleStep(0.05)
        self.spin_smooth.setValue(float(g.get("mouse_smoothing", 0.35)))

        self.spin_sens = QDoubleSpinBox()
        self.spin_sens.setRange(0.3, 2.5)
        self.spin_sens.setSingleStep(0.1)
        self.spin_sens.setValue(float(g.get("mouse_sensitivity", 1.0)))

        self.spin_dead = QSpinBox()
        self.spin_dead.setRange(0, 20)
        self.spin_dead.setValue(int(g.get("mouse_deadzone_px", 2)))

        self.btn_bindings = QPushButton("编辑绑定…")
        self.btn_load = QPushButton("加载配置…")
        self.btn_save = QPushButton("保存配置")

        top = QHBoxLayout()
        top.addWidget(QLabel("模式:"))
        top.addWidget(self.mode_box)
        top.addSpacing(8)
        top.addWidget(self.preview_toggle)
        top.addWidget(self.mirror_toggle)
        top.addWidget(self.osd_toggle)
        top.addSpacing(14)
        top.addWidget(self.recog_toggle)
        top.addWidget(self.exec_toggle)
        top.addWidget(self.mouse_move_output_toggle)
        top.addStretch(1)
        top.addWidget(self.btn_bindings)
        top.addWidget(self.btn_load)
        top.addWidget(self.btn_save)

        mouse_row = QHBoxLayout()
        mouse_row.addWidget(QLabel("平滑"))
        mouse_row.addWidget(self.spin_smooth)
        mouse_row.addWidget(QLabel("灵敏度"))
        mouse_row.addWidget(self.spin_sens)
        mouse_row.addWidget(QLabel("死区(px)"))
        mouse_row.addWidget(self.spin_dead)
        mouse_row.addStretch(1)

        layout = QVBoxLayout()
        layout.addLayout(top)
        layout.addLayout(mouse_row)
        layout.addWidget(self.preview)
        self.setLayout(layout)

        # Components
        self.osd = OSD()
        self.dispatcher = Dispatcher(self.cfg, self.state)

        self.mouse = MouseController(MouseParams(
            smoothing=float(self.spin_smooth.value()),
            sensitivity=float(self.spin_sens.value()),
            deadzone_px=int(self.spin_dead.value())
        ))
        self.mouse_worker = MouseMoveWorker(hz=60)
        self.mouse_worker.start()

        self.tracker = BareHandTracker(min_det=0.6, min_track=0.6)
        self.engine = GestureEngine(self.cfg)

        # Camera
        self.cam = CameraThread(
            index=int(g.get("camera_index", 0)),
            width=int(g.get("camera_width", 640)),
            height=int(g.get("camera_height", 480)),
            fps=int(g.get("camera_fps", 30)),
            mirror=bool(g.get("mirror_camera", True))
        )
        self._latest_frame = None
        self.cam.frame_signal.connect(self._on_camera_frame)
        self.cam.start()

        # Timers: render + infer
        self.ui_fps = int(g.get("ui_fps", 24))
        self.infer_fps = int(g.get("infer_fps", 12))
        self._last_infer_ms = 0

        self.timer = QTimer(self)
        self.timer.setInterval(int(1000 / max(10, self.ui_fps)))
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        # Events
        self.preview_toggle.toggled.connect(self._on_preview_toggle)
        self.mirror_toggle.toggled.connect(self._on_mirror_toggle)
        self.osd_toggle.toggled.connect(self._on_osd_toggle)
        self.recog_toggle.toggled.connect(self._on_recog_toggle)
        self.exec_toggle.toggled.connect(self._on_exec_toggle)
        self.mouse_move_output_toggle.toggled.connect(self._on_mouse_move_output_toggle)

        self.spin_smooth.valueChanged.connect(self._on_mouse_params)
        self.spin_sens.valueChanged.connect(self._on_mouse_params)
        self.spin_dead.valueChanged.connect(self._on_mouse_params)

        self.btn_bindings.clicked.connect(self._open_bindings)
        self.btn_load.clicked.connect(self._load_config_dialog)
        self.btn_save.clicked.connect(self._save_config)

        # cache last results (avoid flicker)
        self._last_lm = None
        self._last_static_raw = None
        self._last_scroll = None
        self._last_event = None
        self._last_action = None

    def closeEvent(self, e):
        self.cam.stop()
        self.cam.wait(800)
        self.mouse_worker.stop()
        e.accept()

    def _on_camera_frame(self, frame):
        self._latest_frame = frame

    def _tick(self):
        if self._latest_frame is None:
            return
        frame = self._latest_frame
        h, w = frame.shape[:2]

        now_ms = int(time.time() * 1000)
        do_infer = self.state.recognition_enabled and (now_ms - self._last_infer_ms >= int(1000 / max(5, self.infer_fps)))

        lm = self._last_lm
        raw_static = self._last_static_raw
        scroll = self._last_scroll
        event = None

        if do_infer:
            self._last_infer_ms = now_ms
            scale = float(self.cfg["general"].get("infer_scale", 0.6))
            if 0.2 < scale < 1.0:
                infer = cv2.resize(frame, (int(w * scale), int(h * scale)))
            else:
                infer = frame
                scale = 1.0

            lm2 = self.tracker.process(infer)
            if lm2 is not None and scale != 1.0:
                lm2 = lm2 / scale

            lm = lm2
            event, raw_static, scroll = self.engine.update_bare(lm, self.state)
            self._last_lm = lm
            self._last_static_raw = raw_static
            self._last_scroll = scroll
            self._last_event = event

        # 鼠标移动：只在 mouse_move_mode + 执行ON + 输出ON + 有lm 时输出
        if (self.state.recognition_enabled and self.state.execution_enabled and
            self.state.mouse_move_output_enabled and self.state.mouse_move_mode and lm is not None):
            ix, iy = float(lm[8][0]), float(lm[8][1])
            tgt = self.mouse.compute_target(ix, iy, frame_w=w, frame_h=h)
            if tgt is not None:
                self.mouse_worker.set_target(tgt[0], tgt[1])
            else:
                # 没有有效目标不必invalidate（保留上次也行）；这里选择不强制
                pass
        else:
            self.mouse_worker.invalidate()

        # 连续比例滚动：scroll={"sv":..,"sh":..}
        if self.state.recognition_enabled and scroll and self.state.execution_enabled:
            sv = int(scroll.get("sv", 0))
            sh = int(scroll.get("sh", 0))
            if sv != 0:
                # 纵向滚动
                from control.actions import do_action
                do_action({"type": "scroll_v", "amount": sv}, self.state)
            if sh != 0:
                from control.actions import do_action
                do_action({"type": "scroll_h_shiftwheel", "amount": sh}, self.state)

        # 离散事件：走绑定系统
        if event:
            cd = int(self._gesture_cooldown(event))
            action = self.dispatcher.dispatch(event, cooldown_ms=cd)
            self._last_action = action
            if self.cfg["general"].get("osd_enabled", True) and self.osd_toggle.isChecked():
                self._show_osd(event, action)

        # 预览渲染
        if self.state.camera_preview_enabled:
            vis = frame  # 不 copy，减少CPU
            # 可选：简单标记（少画）
            if lm is not None:
                p = lm[8].astype(int)
                cv2.circle(vis, (p[0], p[1]), 6, (255, 0, 255), -1)
            self._show_frame(vis)
        else:
            # 不 setText，避免 setPixmap/setText 来回导致闪烁
            pass

    def _gesture_cooldown(self, gid: str):
        # gesture_catalog params 优先，否则 general.cooldown
        for it in self.cfg.get("gesture_catalog", []):
            if it.get("id") == gid:
                return it.get("params", {}).get("cooldown_ms", self.cfg["general"].get("cooldown_ms", 450))
        return self.cfg["general"].get("cooldown_ms", 450)

    def _show_osd(self, gesture_id: str, action: dict):
        if action is None:
            act = "无动作"
        elif action.get("type") == "blocked_execution":
            act = "执行关闭"
        else:
            act = action.get("type", "动作")

        text = (
            f"识别:{'ON' if self.state.recognition_enabled else 'OFF'}  "
            f"执行:{'ON' if self.state.execution_enabled else 'OFF'}  "
            f"移动输出:{'ON' if self.state.mouse_move_output_enabled else 'OFF'}  "
            f"移动模式:{'ON' if self.state.mouse_move_mode else 'OFF'}\n"
            f"手势:{gesture_id}  动作:{act}"
        )
        self.osd.show_message(text, ms=900)

    def _show_frame(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        self.preview.setPixmap(pix.scaled(
            self.preview.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation
        ))

    # --- UI toggles ---
    def _on_preview_toggle(self, v):
        self.state.camera_preview_enabled = bool(v)
        self.cfg["general"]["show_camera_preview"] = bool(v)

    def _on_mirror_toggle(self, v):
        self.cfg["general"]["mirror_camera"] = bool(v)
        self.cam.set_mirror(bool(v))

    def _on_osd_toggle(self, v):
        self.cfg["general"]["osd_enabled"] = bool(v)

    def _on_recog_toggle(self, v):
        self.state.recognition_enabled = bool(v)
        self.cfg["general"]["recognition_enabled"] = bool(v)
        if not v:
            self.mouse_worker.invalidate()
            self.mouse.reset()

    def _on_exec_toggle(self, v):
        self.state.execution_enabled = bool(v)
        self.cfg["general"]["execution_enabled"] = bool(v)
        if not v:
            self.mouse_worker.invalidate()

    def _on_mouse_move_output_toggle(self, v):
        self.state.mouse_move_output_enabled = bool(v)
        self.cfg["general"]["mouse_move_output_enabled"] = bool(v)
        if not v:
            self.mouse_worker.invalidate()

    def _on_mouse_params(self, *_):
        self.mouse.update(MouseParams(
            smoothing=float(self.spin_smooth.value()),
            sensitivity=float(self.spin_sens.value()),
            deadzone_px=int(self.spin_dead.value())
        ))
        self.cfg["general"]["mouse_smoothing"] = float(self.spin_smooth.value())
        self.cfg["general"]["mouse_sensitivity"] = float(self.spin_sens.value())
        self.cfg["general"]["mouse_deadzone_px"] = int(self.spin_dead.value())

    def _open_bindings(self):
        dlg = BindingEditor(self.cfg, parent=self)
        dlg.exec()

    def _load_config_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.cfg = load_config(path)
            QMessageBox.information(self, "加载成功", path)
        except Exception as ex:
            QMessageBox.critical(self, "加载失败", str(ex))

    def _save_config(self):
        try:
            save_config(self.cfg, DEFAULT_CONFIG_PATH)
            QMessageBox.information(self, "保存成功", DEFAULT_CONFIG_PATH)
        except Exception as ex:
            QMessageBox.critical(self, "保存失败", str(ex))
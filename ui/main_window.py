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
from ui.binding_manager import BindingManager
from ui.gesture_catalog_editor import GestureCatalogEditor
from ui.action_catalog_viewer import ActionCatalogViewer
from ui.glove_calibration import GloveCalibrationDialog
from ui.custom_gesture_recorder import CustomGestureRecorder

from vision.camera import CameraThread
from vision.bare_mediapipe import BareHandTracker
from vision.gesture_engine import GestureEngine
from vision.glove_tracker_c import GloveTrackerC
from vision.dynamic_track import TrackWindow
from vision.custom_gestures import CustomGestureManager


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("手势控制中心")
        self.resize(1260, 840)

        self.cfg = load_config(DEFAULT_CONFIG_PATH)
        g = self.cfg["general"]

        self.state = SystemState(
            recognition_enabled=bool(g.get("recognition_enabled", True)),
            execution_enabled=bool(g.get("execution_enabled", True)),
            camera_preview_enabled=bool(g.get("show_camera_preview", True)),
            camera_device_enabled=True,  # 默认开启设备
            mouse_move_output_enabled=bool(g.get("mouse_move_output_enabled", True)),
        )

        # UI
        self.preview = QLabel("预览")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background:#111; color:#bbb;")
        self.preview.setMinimumHeight(560)

        self.mode_box = QComboBox()
        self.mode_box.addItems(["bare", "glove"])

        self.preview_toggle = QCheckBox("显示预览")
        self.preview_toggle.setChecked(self.state.camera_preview_enabled)

        self.camera_device_toggle = QCheckBox("摄像头设备 ON")
        self.camera_device_toggle.setChecked(True)

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

        self.btn_record_custom = QPushButton("录制自定义动态手势…")
        self.btn_gestures = QPushButton("手势字典…")
        self.btn_actions = QPushButton("动作字典…")
        self.btn_bindings = QPushButton("绑定管理…")
        self.btn_glove_calib = QPushButton("手套校准…")
        self.btn_load = QPushButton("加载配置…")
        self.btn_save = QPushButton("保存配置")

        top = QHBoxLayout()
        top.addWidget(QLabel("模式:"))
        top.addWidget(self.mode_box)
        top.addSpacing(10)
        top.addWidget(self.camera_device_toggle)
        top.addWidget(self.preview_toggle)
        top.addWidget(self.mirror_toggle)
        top.addWidget(self.osd_toggle)
        top.addSpacing(14)
        top.addWidget(self.recog_toggle)
        top.addWidget(self.exec_toggle)
        top.addWidget(self.mouse_move_output_toggle)
        top.addStretch(1)
        top.addWidget(self.btn_record_custom)
        top.addWidget(self.btn_bindings)
        top.addWidget(self.btn_gestures)
        top.addWidget(self.btn_actions)
        top.addWidget(self.btn_glove_calib)
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

        glove_cfg = self.cfg.get("glove", {})
        self.glove = GloveTrackerC(
            hsv_lower=tuple(glove_cfg.get("hsv_lower", [20, 80, 80])),
            hsv_upper=tuple(glove_cfg.get("hsv_upper", [40, 255, 255])),
            erode=int(glove_cfg.get("erode", 1)),
            dilate=int(glove_cfg.get("dilate", 2)),
            min_area=int(glove_cfg.get("min_area", 1500))
        )

        self.engine = GestureEngine(self.cfg)

        # 自定义动态手势
        self.custom_mgr = CustomGestureManager(self.cfg)
        self._custom_track = TrackWindow(window_ms=600)
        self._recorder = None

        self._glove_dialog = None

        # Camera device (可开关)
        self.cam = None
        self._latest_frame = None
        self._start_camera()

        # Timers
        self.ui_fps = int(g.get("ui_fps", 24))
        self.infer_fps = int(g.get("infer_fps", 12))
        self._last_infer_ms = 0

        self.timer = QTimer(self)
        self.timer.setInterval(int(1000 / max(10, self.ui_fps)))
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        # Cache
        self._last_lm = None
        self._last_glove_feats = None
        self._last_raw_static = None
        self._last_scroll = None

        # Events
        self.preview_toggle.toggled.connect(self._on_preview_toggle)
        self.camera_device_toggle.toggled.connect(self._on_camera_device_toggle)
        self.mirror_toggle.toggled.connect(self._on_mirror_toggle)
        self.osd_toggle.toggled.connect(self._on_osd_toggle)
        self.recog_toggle.toggled.connect(self._on_recog_toggle)
        self.exec_toggle.toggled.connect(self._on_exec_toggle)
        self.mouse_move_output_toggle.toggled.connect(self._on_mouse_move_output_toggle)

        self.spin_smooth.valueChanged.connect(self._on_mouse_params)
        self.spin_sens.valueChanged.connect(self._on_mouse_params)
        self.spin_dead.valueChanged.connect(self._on_mouse_params)

        self.btn_bindings.clicked.connect(self._open_binding_manager)
        self.btn_gestures.clicked.connect(self._open_gestures)
        self.btn_actions.clicked.connect(self._open_actions)
        self.btn_glove_calib.clicked.connect(self._open_glove_calib)
        self.btn_record_custom.clicked.connect(self._open_recorder)

        self.btn_load.clicked.connect(self._load_config_dialog)
        self.btn_save.clicked.connect(self._save_config)

    def closeEvent(self, e):
        self._stop_camera()
        self.mouse_worker.stop()
        e.accept()

    # ---------- Camera device control ----------
    def _start_camera(self):
        if self.cam is not None:
            return
        g = self.cfg["general"]
        self.state.camera_device_enabled = True
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

    def _stop_camera(self):
        if self.cam is None:
            return
        try:
            self.cam.stop()
            self.cam.wait(800)
        except Exception:
            pass
        self.cam = None
        self._latest_frame = None
        self.state.camera_device_enabled = False
        self.preview.clear()
        self.preview.setText("摄像头已关闭")
        self.preview.setStyleSheet("background:#111; color:#bbb;")

    def _on_camera_frame(self, frame):
        self._latest_frame = frame
        if self._glove_dialog is not None and self._glove_dialog.isVisible():
            self._glove_dialog.update_frame(frame)

    # ---------- Custom gesture recorder ----------
    def _open_recorder(self):
        self._recorder = CustomGestureRecorder(self)
        if self._recorder.exec() == self._recorder.Accepted:
            gid, pts = self._recorder.get_result()
            mode = self.mode_box.currentText()
            ok = self.custom_mgr.add_template(gid, mode=mode, raw_points=pts)
            if ok:
                if not any(x.get("id") == gid for x in self.cfg.get("gesture_catalog", [])):
                    self.cfg["gesture_catalog"].append({
                        "id": gid,
                        "title": f"自定义:{gid}",
                        "type": "dynamic",
                        "mode": mode,
                        "description": "自定义动态模板手势",
                        "default_use": "custom_bind",
                        "notes": "",
                        "enable_when": {},
                        "params": {"cooldown_ms": 600}
                    })
                QMessageBox.information(self, "成功", f"已保存自定义手势：{gid}")
            else:
                QMessageBox.warning(self, "失败", "保存模板失败（轨迹不足或数据异常）")

    # ---------- Tick ----------
    def _tick(self):
        # 摄像头设备关闭时，无帧
        if self._latest_frame is None:
            return

        frame = self._latest_frame
        h, w = frame.shape[:2]

        now_ms = int(time.time() * 1000)
        do_infer = self.state.recognition_enabled and self.state.camera_device_enabled and (
            now_ms - self._last_infer_ms >= int(1000 / max(5, self.infer_fps))
        )

        event = None
        raw_static = self._last_raw_static
        scroll = self._last_scroll

        mode = self.mode_box.currentText()

        if do_infer:
            self._last_infer_ms = now_ms

            scale = float(self.cfg["general"].get("infer_scale", 0.6))
            if 0.2 < scale < 1.0:
                infer = cv2.resize(frame, (int(w * scale), int(h * scale)))
            else:
                infer = frame
                scale = 1.0

            if mode == "bare":
                lm2 = self.tracker.process(infer)
                if lm2 is not None and scale != 1.0:
                    lm2 = lm2 / scale
                self._last_lm = lm2
                self._last_glove_feats = None

                # 自定义轨迹采样 + 录制喂点
                if lm2 is not None:
                    self._custom_track.add(float(lm2[8][0]), float(lm2[8][1]))
                    if self._recorder is not None and self._recorder.isVisible() and self._recorder.recording:
                        self._recorder.add_point(float(lm2[8][0]), float(lm2[8][1]))

                event, raw_static, scroll = self.engine.update_bare(lm2, self.state)

                # 自定义匹配：仅在没有事件/滚动时尝试
                if event is None and (scroll is None) and lm2 is not None:
                    pts = np.array([(x, y) for _, x, y in self._custom_track.pts], dtype=np.float32) \
                        if len(self._custom_track.pts) >= 12 else None
                    if pts is not None:
                        thr = float(self.cfg["general"].get("custom_match_threshold", 0.22))
                        m = self.custom_mgr.match(mode="bare", raw_points=pts, threshold=thr)
                        if m:
                            gid, _dist = m
                            event = gid

            else:
                feats = self.glove.process(infer)
                if scale != 1.0 and feats.center is not None:
                    feats.center = (int(feats.center[0] / scale), int(feats.center[1] / scale))
                    feats.fingertips = [(int(x / scale), int(y / scale)) for x, y in feats.fingertips]
                self._last_glove_feats = feats
                self._last_lm = None

                event, raw_static, scroll = self.engine.update_glove(feats, self.state)

            self._last_raw_static = raw_static
            self._last_scroll = scroll

        # 鼠标移动输出：仍用 mouse_move_mode 控制
        can_move = (
            self.state.camera_device_enabled and self.state.recognition_enabled and self.state.execution_enabled and
            self.state.mouse_move_output_enabled and self.state.mouse_move_mode
        )
        if can_move:
            if mode == "bare" and self._last_lm is not None:
                x, y = float(self._last_lm[8][0]), float(self._last_lm[8][1])
                tgt = self.mouse.compute_target(x, y, frame_w=w, frame_h=h)
                if tgt:
                    self.mouse_worker.set_target(tgt[0], tgt[1])
            elif mode == "glove" and self._last_glove_feats is not None and self._last_glove_feats.center is not None:
                cx, cy = self._last_glove_feats.center
                tgt = self.mouse.compute_target(float(cx), float(cy), frame_w=w, frame_h=h)
                if tgt:
                    self.mouse_worker.set_target(tgt[0], tgt[1])
        else:
            self.mouse_worker.invalidate()

        # 滚动连续输出（不需要绑定也会输出？——不，仍需用户绑定动作才执行）
        # 注意：你现在要求“默认绑定全部取消”，所以我们这里不直接调用 do_action。
        # 我们改成：把 scroll 转换成两个“虚拟事件”，交由绑定系统决定是否执行。
        if scroll and self.state.execution_enabled:
            sv = int(scroll.get("sv", 0))
            sh = int(scroll.get("sh", 0))
            # 只有用户绑定了这些事件才会执行
            if sv != 0:
                self.dispatcher.dispatch("__SCROLL_V__", cooldown_ms=0, extra_payload={"amount": sv})
            if sh != 0:
                self.dispatcher.dispatch("__SCROLL_H__", cooldown_ms=0, extra_payload={"amount": sh})

        # 离散事件 -> 绑定执行
        if event:
            cd = int(self._gesture_cooldown(event))
            action = self.dispatcher.dispatch(event, cooldown_ms=cd)

            # 若动作是 toggle_camera_device，则在这里执行设备开关（UI线程）
            if action and action.get("type") == "toggle_camera_device":
                self._toggle_camera_device()

            if self.cfg["general"].get("osd_enabled", True) and self.osd_toggle.isChecked():
                self._show_osd(mode, event, action)

        # 预览渲染
        if self.state.camera_preview_enabled:
            vis = frame
            if mode == "bare" and self._last_lm is not None:
                p = self._last_lm[8].astype(int)
                cv2.circle(vis, (p[0], p[1]), 6, (255, 0, 255), -1)
            if mode == "glove" and self._last_glove_feats is not None:
                feats = self._last_glove_feats
                if feats.center:
                    cv2.circle(vis, feats.center, 7, (255, 255, 0), -1)
                for x, y in feats.fingertips:
                    cv2.circle(vis, (x, y), 7, (0, 0, 255), -1)
            self._show_frame(vis)
        else:
            if self.preview.pixmap() is not None:
                self.preview.clear()
                self.preview.setText("预览已关闭（识别仍在后台运行）")
                self.preview.setStyleSheet("background:#111; color:#bbb;")

    def _toggle_camera_device(self):
        if self.state.camera_device_enabled:
            self.camera_device_toggle.blockSignals(True)
            self.camera_device_toggle.setChecked(False)
            self.camera_device_toggle.blockSignals(False)
            self._stop_camera()
        else:
            self.camera_device_toggle.blockSignals(True)
            self.camera_device_toggle.setChecked(True)
            self.camera_device_toggle.blockSignals(False)
            self._start_camera()

    def _gesture_cooldown(self, gid: str):
        for it in self.cfg.get("gesture_catalog", []):
            if it.get("id") == gid:
                return it.get("params", {}).get("cooldown_ms", self.cfg["general"].get("cooldown_ms", 450))
        return self.cfg["general"].get("cooldown_ms", 450)

    def _show_osd(self, mode: str, gesture_id: str, action: dict):
        if action is None:
            act = "无动作"
        elif action.get("type") == "blocked_execution":
            act = "执行关闭"
        else:
            act = action.get("type", "动作")

        text = (
            f"模式:{mode} 识别:{'ON' if self.state.recognition_enabled else 'OFF'} "
            f"执行:{'ON' if self.state.execution_enabled else 'OFF'} "
            f"设备:{'ON' if self.state.camera_device_enabled else 'OFF'} "
            f"预览:{'ON' if self.state.camera_preview_enabled else 'OFF'} "
            f"移动输出:{'ON' if self.state.mouse_move_output_enabled else 'OFF'} "
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

    # ---------- UI handlers ----------
    def _on_preview_toggle(self, v):
        self.state.camera_preview_enabled = bool(v)
        self.cfg["general"]["show_camera_preview"] = bool(v)
        if not v:
            self.preview.clear()
            self.preview.setText("预览已关闭（识别仍在后台运行）")
            self.preview.setStyleSheet("background:#111; color:#bbb;")

    def _on_camera_device_toggle(self, v):
        if v:
            self._start_camera()
        else:
            self._stop_camera()

    def _on_mirror_toggle(self, v):
        self.cfg["general"]["mirror_camera"] = bool(v)
        if self.cam is not None:
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

    def _open_binding_manager(self):
        dlg = BindingManager(self.cfg, parent=self)
        dlg.exec()

    def _open_gestures(self):
        dlg = GestureCatalogEditor(self.cfg, parent=self)
        dlg.exec()

    def _open_actions(self):
        dlg = ActionCatalogViewer(self.cfg, parent=self)
        dlg.exec()

    def _open_glove_calib(self):
        if self._glove_dialog is None:
            self._glove_dialog = GloveCalibrationDialog(self.cfg, parent=self)
        self._glove_dialog.show()
        self._glove_dialog.raise_()

    def _load_config_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "加载配置", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.cfg = load_config(path)
            self.dispatcher = Dispatcher(self.cfg, self.state)
            self.engine = GestureEngine(self.cfg)
            self.custom_mgr = CustomGestureManager(self.cfg)

            glove_cfg = self.cfg.get("glove", {})
            self.glove.update_hsv(glove_cfg.get("hsv_lower", [20, 80, 80]), glove_cfg.get("hsv_upper", [40, 255, 255]))

            QMessageBox.information(self, "加载成功", path)
        except Exception as ex:
            QMessageBox.critical(self, "加载失败", str(ex))

    def _save_config(self):
        try:
            save_config(self.cfg, DEFAULT_CONFIG_PATH)
            QMessageBox.information(self, "保存成功", DEFAULT_CONFIG_PATH)
        except Exception as ex:
            QMessageBox.critical(self, "保存失败", str(ex))
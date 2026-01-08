## 开发任务表格（Markdown）

> 字段说明：
>
> - **P0/P1/P2**：优先级（P0 必须先做）
> - **依赖**：前置任务编号
> - **验收标准**：可测试的完成条件

| ID    | 优先级 | 模块         | 任务                                                         | 交付物                             | 依赖              | 验收标准                                          |
| ----- | ------ | ------------ | ------------------------------------------------------------ | ---------------------------------- | ----------------- | ------------------------------------------------- |
| T-001 | P0     | 工程         | 初始化项目结构与模块划分（ui/vision/control/config）         | 可运行工程骨架                     | -                 | `python app.py` 可启动并正常退出                  |
| T-002 | P0     | 配置         | 定义配置总结构：Gesture Catalog / Action Catalog / Bindings（全局/按应用） | `default_config.json` + schema草案 | T-001             | 配置可加载/保存；缺字段能用默认值补齐             |
| T-003 | P0     | 配置         | 配置校验与合并（默认合并 + schema校验）                      | `config/io.py`、`schema.json`      | T-002             | 错配时给出清晰报错；不崩溃                        |
| T-004 | P0     | 摄像         | 摄像采集线程：设置 640×480@30、镜像开关、仅推送帧            | `vision/camera.py`                 | T-001             | 画面稳定；镜像切换生效；无闪烁                    |
| T-005 | P0     | 性能         | 推理/渲染解耦：缓存最新帧 + QTimer 渲染；推理限频10–15fps    | UI 主循环改造                      | T-004             | UI 不闪烁；推理频率稳定；无帧堆积卡顿             |
| T-006 | P0     | UI           | 主窗口基础控件：模式切换、显示摄像开关、镜像、OSD、识别开关、执行开关、启用鼠标移动开关、配置加载/保存 | `ui/main_window.py`                | T-001,T-002       | 各开关互不串扰；关闭预览不影响识别                |
| T-007 | P0     | UI           | OSD 悬浮窗：显示模式/手势/动作/识别ON/OFF/执行ON/OFF         | `ui/osd.py`                        | T-006             | 触发时显示正确；频繁触发不导致卡顿                |
| T-008 | P0     | 裸手视觉     | MediaPipe Hands 接入，输出关键点（支持 infer_scale 映射回原坐标） | `vision/hand_bare_mediapipe.py`    | T-005             | 关键点稳定；infer_scale 后坐标正确                |
| T-009 | P0     | 手势引擎     | 通用识别原语库（距离、捏合、并拢、轨迹、stable_frames、cooldown、enable_when） | `vision/gesture_primitives.py`     | T-008             | 可用配置参数驱动识别，不写死用途                  |
| T-010 | P0     | 手势引擎     | 基于 Gesture Catalog 的识别执行：产出 gesture_event（支持启用条件与优先级） | `vision/gesture_engine.py`         | T-009,T-002       | 新增/禁用手势无需改代码即可生效（在可表达范围内） |
| T-011 | P0     | 动作执行     | Action Catalog 与执行器：key/hotkey/scroll_v/open_program/shell/click/双击/右键/拖拽 | `control/actions.py`               | T-002             | 各动作可执行且参数校验正确；无窗口聚焦功能        |
| T-012 | P0     | 状态         | 系统状态管理：recognition_enabled / execution_enabled / preview_enabled / mouse_move_output_enabled / mouse_move_mode | `control/state.py`                 | T-006             | UI 与内部状态同步；状态可持久化到配置             |
| T-013 | P0     | 指令派发     | Dispatcher：按应用覆盖全局；识别/执行开关门控；toggle动作永远可用 | `control/dispatcher.py`            | T-011,T-012       | 执行关闭时仅显示不执行；toggle_execution 仍可恢复 |
| T-014 | P0     | 默认交互     | 预置关键手势条目与默认绑定：OPEN_PALM=neutral、THUMBS_UP=toggle_recognition、V_SIGN=鼠标移动启用等 | 默认 preset                        | T-002,T-010,T-013 | 默认配置开箱可用，且可在 UI 中修改/删除           |
| T-015 | P0     | 鼠标移动     | MouseMoveWorker 后台线程限频 moveTo + invalidate 机制（避免卡死、允许接管） | `control/mouse_worker.py`          | T-012             | 不再卡死；停止移动姿势后实体鼠标可接管            |
| T-016 | P0     | 鼠标映射     | 指尖→屏幕映射：平滑/灵敏度/死区；与镜像策略一致不反向        | `control/mouse_controller.py`      | T-015,T-006       | 移动方向与画面一致；参数调整生效                  |
| T-017 | P0     | 鼠标模式手势 | 右键：拇指+中指捏合（PINCH_RIGHT_CLICK）；双击：食指+中指并拢（INDEX_MIDDLE_DOUBLE_CLICK） | Gesture条目+识别规则               | T-010             | 仅在 mouse_move_mode 时触发；可改绑/禁用          |
| T-018 | P0     | 滚动         | 比例滚动状态机（PINCH_SCROLL）：速度与位移成比例；纵向dy控制 | `vision/scroll_state.py`           | T-010             | 滚动随位移变化平滑；抖动有死区                    |
| T-019 | P0     | 横向滚动     | 横向滚动方案2：Shift+Wheel（dx控制方向与幅度）               | 动作类型实现                       | T-011,T-018       | 常见应用中横滚生效；可配置比例系数/上限           |
| T-020 | P0     | 动态滑动     | SWIPE_* 动态手势保留（供用户自定义绑定）                     | Gesture条目                        | T-010             | 可绑定翻页/快捷键，触发稳定                       |
| T-021 | P1     | UI           | 手势字典窗口：展示/编辑手势ID、描述、默认用途、备注、类型、模式、条件、参数 | `ui/gesture_catalog_editor.py`     | T-002,T-010       | 可增删改、启用/禁用；保存后生效                   |
| T-022 | P1     | UI           | 动作字典窗口：展示动作类型、参数schema、示例（可编辑描述/示例） | `ui/action_catalog_viewer.py`      | T-002,T-011       | 用户可查阅每种动作参数格式                        |
| T-023 | P1     | UI           | 绑定编辑器升级：支持全局/按应用、参数表单/JSON双模式、导入导出preset | `ui/binding_editor.py`             | T-002,T-013       | 按应用覆盖全局正确；导入导出可用                  |
| T-024 | P1     | 按应用绑定   | 前台进程名获取（Windows优先）并与绑定匹配                    | `control/app_context.py`           | T-013             | 不崩溃；识别进程名准确（Windows）                 |
| T-025 | P1     | 自定义手势   | 录制轨迹模板+归一化+匹配；写入 Gesture Catalog/模板库        | `vision/custom_gestures.py`        | T-010             | 用户录制后可识别并可绑定动作                      |
| T-026 | P1     | 手套模式C    | HSV分割+形态学+最大轮廓ROI+中心/指尖候选输出                 | `vision/hand_glove_seg.py`         | T-004             | 校准后识别稳定；特征输出符合接口                  |
| T-027 | P1     | 手套校准     | HSV 校准窗口（ROI采样分位数）并写回配置                      | `ui/glove_calibration.py`          | T-026,T-006       | 校准后效果明显；重启后保留                        |
| T-028 | P1     | 手套手势     | 手套模式下复用 gesture_engine（用 glove features 适配）      | 适配层                             | T-026,T-010       | glove 模式也能触发同一套手势ID                    |
| T-029 | P2     | 手套扩展     | 方案C预留“轻量分割模型”接口（Segmenter stub + 可插拔）       | `vision/segmenter_base.py`         | T-026             | 不接模型也可跑；接入时只改配置                    |
| T-030 | P2     | 手套扩展     | 方案B预留：MarkerTracker 接口与占位实现 + UI入口（可置灰）   | `vision/marker_tracker.py`         | T-026             | 切换到B不崩溃；接口文档明确                       |
| T-031 | P2     | 体验         | 实体鼠标接管保护（检测外力移动暂停worker输出）               | worker增强                         | T-015             | 手动移动鼠标时不会被拉回                          |
| T-032 | P2     | 体验         | 手势冲突优先级策略配置化（state > composite > dynamic > static > neutral） | 配置项+实现                        | T-010             | 冲突时行为可预测且可配置                          |
| T-033 | P2     | 测试         | 功能测试用例清单 + 回归脚本（基础）                          | `TESTS.md`                         | T-014             | 覆盖开关、鼠标模式、滚动、绑定、手套校准          |
| T-034 | P2     | 文档         | 用户手册：校准、编辑手势/绑定、开关说明、性能建议            | `README.md`                        | T-014,T-027       | 新用户按文档可完成配置与使用                      |

------

### 备注：关键“不可写死”要求落点

- “手势名称/描述/用途/备注/阈值/启用条件/绑定关系”全部落在 **T-002/T-010/T-021/T-023**。
- 默认行为仅作为 preset（T-014），用户可在 UI 中增删改。
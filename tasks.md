# 0. 项目里程碑与交付节奏

## M1 可用原型（核心跑通）

- 裸手识别 + OSD + 识别/执行/预览/鼠标移动开关
- 绑定系统（全局）+ 动作执行器（基础动作）
- 性能解耦（不闪烁，CPU 可控）

## M2 功能完善（参考项目交互对齐）

- 鼠标移动模式与复合手势：右键捏合/双击/比例滚动
- 动态滑动手势保留并可绑定
- 按应用绑定（进程名覆盖）
- 自定义手势录制与模板匹配

## M3 手套模式增强（方案C落地 + 预留B）

- HSV 校准 + 方案C几何特征识别
- 轻量分割模型接口预留（可先 stub）
- MarkerTracker（方案B）接口预留（stub + 文档）

------

# 1. 基础工程与配置体系

## 1.1 项目骨架与模块划分

**任务**

- 建立目录结构：`ui/ vision/ control/ config/ assets/`
- 统一日志与异常处理（控制台+可选文件）

**验收**

- `python app.py` 可启动主窗口，退出无崩溃
- 模块间依赖清晰（UI 不直接做重推理）

## 1.2 配置模型与 Schema（全可编辑的关键）

**任务**

- 定义并实现三类配置表：
  1. Gesture Catalog（手势目录）
  2. Action Catalog（动作目录）
  3. Bindings（全局/按应用）
- 提供默认配置 preset
- 提供 JSON schema（用于校验与 UI 表单生成）

**验收**

- 配置文件可加载/保存/导入/导出
- 删除/新增手势、动作、绑定不会导致程序崩溃（无硬编码依赖）

------

# 2. UI 模块（PyQt6）

## 2.1 主窗口

**任务**

- 控件：
  - 模式切换：裸手/手套
  - 显示摄像开关（preview）
  - 镜像开关
  - OSD 开关
  - 识别开关（Recognition）
  - 执行开关（Execution）
  - 启用鼠标移动开关（Mouse Move Output）
  - 鼠标参数：平滑/灵敏度/死区
  - 配置加载/保存
- 状态显示：
  - recognition_enabled / execution_enabled / preview_enabled / mouse_move_output_enabled / mouse_move_mode

**验收**

- 各开关生效且互不串扰：
  - 关闭预览不影响识别
  - 关闭执行仍识别但不执行动作
  - 关闭识别不推理且不执行

## 2.2 OSD 悬浮窗

**任务**

- 置顶透明 OSD：显示模式/手势/动作/状态（ON/OFF）
- 显示节流（避免频繁刷新导致卡顿）

**验收**

- 触发手势时 OSD 正确显示，且不会闪烁/卡住 UI

## 2.3 手势字典窗口（必须）

**任务**

- 表格展示与编辑：
  - 手势ID、名称、类型、模式、描述、默认用途、备注、启用条件、参数（可弹窗编辑）
- 支持增删改、启用/禁用、导入导出（可与主配置共用）

**验收**

- 用户可新增一个手势条目并保存，重启后仍存在
- 禁用某手势后不会再触发

## 2.4 动作字典窗口（必须）

**任务**

- 展示动作类型、参数 schema、示例
- 支持扩展（至少展示，不一定允许用户新增“新动作类型”代码级能力；但允许修改描述与预设）

**验收**

- 用户能看到每种动作需要的参数格式

## 2.5 绑定编辑器（全局/按应用）

**任务**

- 选择范围：全局 / 应用进程名
- 每条绑定：gesture_id → action_type + params
- 导入导出 preset

**验收**

- 全局绑定与按应用绑定覆盖逻辑正确
- 可编辑并实时生效（或提示保存后生效）

## 2.6 手套 HSV 校准窗口

**任务**

- 中央 ROI 采样估计 HSV lower/upper
- 写入配置并即时生效

**验收**

- 校准后手套 mask 明显改善，重启后参数保留

------

# 3. 摄像与性能架构（解决闪烁/高CPU）

## 3.1 摄像采集线程

**任务**

- 采集分辨率固定：默认 640×480@30
- 镜像可切换
- 只发帧，不做推理

**验收**

- 摄像画面稳定，无“闪一闪”现象

## 3.2 推理与渲染解耦（关键）

**任务**

- 相机线程：缓存最新帧
- UI QTimer：固定刷新（20–30fps）
- 推理节流：10–15fps，infer_scale（0.5–0.7）
- 非推理帧复用上次识别结果（避免抖动）
- Qt 缩放 FastTransformation

**验收**

- 预览开启时不卡顿、不闪烁
- CPU 较初版明显下降（至少可观察到降低趋势）
- 关闭预览后 CPU 进一步下降（渲染负载减少）

------

# 4. 视觉识别（裸手/手套）

## 4.1 裸手：MediaPipe Hands

**任务**

- 获取关键点与手性（可选）
- 提供基础特征计算原语：
  - 指尖/关节距离
  - 捏合距离（拇指-食指、拇指-中指）
  - 两指并拢距离（食指-中指）
  - 轨迹点（用于 swipe 与比例滚动）

**验收**

- 手进入/离开画面鲁棒
- 关键点映射到原图坐标正确（infer_scale 后）

## 4.2 手套：方案 C（先实现）

**任务**

- HSV 分割 + 形态学
- 最大轮廓 + ROI
- 几何特征：中心、凸包、指尖候选、指数量
- 接口预留：`Segmenter`（轻量分割模型，可先 stub 返回 None）
- 识别结果转换成统一的“特征对象”，供手势引擎使用

**验收**

- 在校准后，能稳定获得中心点与粗指尖信息
- 不引入明显额外卡顿

## 4.3 方案 B 预留接口（不要求立即实现）

**任务**

- 定义 `MarkerTracker` 抽象接口与占位实现（返回空）
- UI 中保留“Glove Backend：C / B（实验）”入口（B 可置灰）
- 文档说明如何扩展 B（彩色点/Tag）

**验收**

- 切换到 B 不崩溃（即使无输出）
- 代码结构可插拔

------

# 5. 手势引擎（全配置化）

## 5.1 手势识别算子库（Primitive Operators）

**任务**
实现可组合的通用算子（不要写死具体手势）：

- 静态算子：
  - finger_extended（基于关键点）
  - distance(a,b) / distance_ratio(a,b,scale)
  - pinch(thumb, index/middle) 阈值判定
  - two_finger_close(index, middle) 判定
- 动态算子：
  - swipe_direction（轨迹窗口）
  - pinch_scroll_state（进入/保持/退出）
  - proportional_scroll_delta（dx/dy → scroll量）
- 通用防抖：
  - stable_frames
  - cooldown_ms
- enable_when 条件：
  - recognition_enabled / execution_enabled / mouse_move_mode / etc

**验收**

- 新增/修改手势目录中的规则后，无需改代码即可生效（在可表达范围内）

## 5.2 默认手势目录（可编辑预置）

**任务**
在 Gesture Catalog 中提供预置条目（用户可删改）：

- OPEN_PALM（neutral）
- THUMBS_UP（toggle_recognition）
- V_SIGN（mouse_move_mode enable/hold）
- PINCH_RIGHT_CLICK（thumb+middle pinch）
- INDEX_MIDDLE_DOUBLE_CLICK（index+middle close）
- PINCH_SCROLL（thumb+index pinch，比例滚动）
- SWIPE_*（动态滑动）
- OK_SIGN/FIST（可作为拖拽等示例）

**验收**

- 用户可在“手势字典窗口”看到这些条目并修改参数

## 5.3 自定义手势录制（动态模板）

**任务**

- 录制轨迹点
- 归一化：重采样、平移、缩放
- 模板匹配：距离阈值可配置
- 自定义条目写入 Gesture Catalog + 自定义模板库

**验收**

- 用户录制后能识别该自定义手势并可绑定动作

------

# 6. 动作执行器（I/O 输出）

## 6.1 动作目录（Action Catalog）与执行器实现

**任务**
实现动作类型（不包含窗口聚焦）：

- toggle_recognition
- toggle_execution
- toggle_camera_preview（可选但建议）
- toggle_mouse_move_output
- key / hotkey
- scroll_v
- scroll_h_shiftwheel（横向滚动方案2）
- click_left / double_click_left / click_right
- mouse_down_left / mouse_up_left
- open_program
- shell

**验收**

- 执行开关关闭时：除 toggle_execution 外全部不执行
- 识别开关关闭时：不识别不执行
- 横向滚动按 Shift+Wheel 生效（在常见应用可用）

## 6.2 鼠标移动注入（后台线程限频）

**任务**

- MouseMoveWorker：30–60Hz moveTo
- 仅在以下条件同时满足才输出：
  - recognition_enabled=true
  - execution_enabled=true
  - mouse_move_output_enabled=true
  - mouse_move_mode=true（或满足 enable_when）
- 否则 invalidate，确保实体鼠标可接管
- 可选：物理鼠标接管保护（检测外力移动暂停输出）

**验收**

- 不再出现“卡死”
- 停止移动姿势后能立即用实体鼠标

------

# 7. 绑定与覆盖逻辑

## 7.1 绑定解析

**任务**

- gesture_event → 查找按应用绑定（若命中）→ 否则全局绑定
- 事件冲突处理（同一时刻多个手势）：
  - 状态型优先（滚动模式/拖拽）
  - 复合点击次之（右键/双击）
  - swipe 再次之
  - neutral 最后（通常不触发动作）

**验收**

- 按应用覆盖全局正确
- 不会因中立/开关导致其他动作误触发

------

# 8. 质量与测试任务

## 8.1 功能测试用例（必须编写）

**任务**

- 识别开关：THUMBS_UP 开/关识别
- 执行开关：toggle_execution 后只显示不执行
- 预览开关：关闭预览仍识别，CPU 降低
- 鼠标移动开关：关闭后不再 moveTo
- 鼠标模式手势：
  - 右键捏合触发
  - 双击触发
  - 比例滚动（纵向/横向）
- swipe 手势可绑定并触发

**验收**

- 每条用例通过并可录屏复现

## 8.2 性能基线

**任务**

- 记录 CPU 占用与帧率（预览开/关、识别开/关）
- 确认无闪烁、无明显输入延迟

**验收**

- 性能优化项全部启用时明显优于初版（主观流畅 + 客观指标有改善）

------

# 9. 文档与交付物

**交付物**

- 用户手册（如何校准手套、如何编辑手势/绑定、如何启停识别/执行/预览/鼠标移动）
- 配置说明（Gesture Catalog / Action Catalog / Bindings 格式）
- 开发文档（模块接口、如何新增动作、如何实现方案B MarkerTracker）
- 默认 preset（至少 1 套“通用办公”，可选 1 套“PPT演示”）
## 目标概述
- 在“总览表”区域增加行列切换按钮与“导出”下拉菜单，满足 PDF/CSV/Excel/Markdown 导出、移动端适配、大数据量（>1万行）进度提示、加载与错误提示、PDF分页。

## 现有代码与定位
- 表格渲染：`dashboard/app.js:528` 的 `renderPivotTable(selectedInds)` 构建表头、二级表头（化疗周期）与数据行；容器：`dashboard/index.html:48` 的 `#pivotTable`。
- 日期格式与周期标签：`dashboard/app.js:152` `computePhaseLabel`、`dashboard/app.js:175` `formatDateDot`。
- 表格样式：`dashboard/styles.css:40-52`（含粘性表头、单元格异常着色）。
- 更新流程：`dashboard/app.js:615-621` `update()` 读取勾选指标与周期范围后调用 `renderPivotTable`。
- 技术栈：原生 HTML/CSS/JS + ECharts；前端无打包工具，可通过 CDN 引入第三方库。

## UI 改动
- 在“总览表”标题右侧新增工具栏（右对齐）：
  - 行列切换按钮（图标 `↔️/↕️`），带 tooltip 文案“切换为日期为行/指标为行”。
  - “导出”下拉菜单按钮，菜单项：PDF、CSV、Excel（.xlsx）、Markdown，每项含对应图标（使用 emoji 或内联 SVG）。
- 工具栏容器放置于 `dashboard/index.html:46-49` 的 `section.table-section` 内，紧邻 `h2` 标题。

## 样式与交互规范
- 新增 `.table-toolbar`、`.btn`、`.btn-icon`、`.dropdown`、`.dropdown-menu`、`.tooltip` 样式，保持与现有卡片/控件一致的边框、圆角、阴影与悬停/点击反馈（参考 `styles.css` 基础色与边框风格）。
- 响应式：
  - ≥1024px：工具栏右对齐并与标题同一行。
  - 600–1024px：工具栏换行，按钮尺寸缩小但保留可点区域。
  - <600px：下拉菜单宽度为满宽，增大触控区域。

## 行列切换实现
- 新增状态 `isTransposed`（模块级变量），默认 false（指标为行、日期为列）。
- 抽象数据模型：新增 `buildPivotModel(selectedInds)`，产出：
  - `rowHeaders`、`colHeaders`（含一级：名称/日期；二级：周期标签）。
  - `cells`（二维数组，含 `value` 与 `flag`）。
- 切换逻辑：
  - `transposeModel(model)` 交换 `rowHeaders` 与 `colHeaders`，并转置 `cells`。
  - `renderPivotTable(selectedInds)` 改造为依据 `isTransposed` 渲染两种结构：
    - 非转置：沿用现有表头二行（第一行日期，第二行周期）；行首两列为“检测指标”“参考范围”。
    - 转置：首列为日期，第二列为周期；列首两列为“检测日期”“所属化疗周期”，随后各指标成为列，顶部追加单位/参考范围说明（合并为表头第二行）。
- 过渡动画：
  - 表格替换前后为容器添加/移除 `fade-in` 类（CSS `opacity` 与 `transform` 过渡），实现平滑切换。
- 状态保留：排序/筛选当前项目在本页为“勾选指标 + 周期范围”与数据缺失处理，切换时不改变 `selectedInds`、`startCycle`、`endCycle`，保持 `update()` 流程不变。

## 导出功能设计
- 数据收集：新增 `collectPivotData(selectedInds, isTransposed)` 返回二维数组（含表头多行），统一给各导出函数使用。
- 文件命名：`pivot-YYYY-MM-DD.{pdf|csv|xlsx|md}`，日期基于当前 `new Date()`。
- CSV（UTF-8+BOM）：
  - 将二维数组串行化为 CSV，必要时对含逗号/换行进行引号包裹。
  - 大数据量采用分块串接（见进度管理）。
- Excel（.xlsx）：
  - 通过 CDN 引入 `exceljs`，新建工作簿与工作表，写入二维数组。
  - 表头样式：加粗、居中、浅灰背景、冻结首行/首列，列宽自适应；保留单位/参考范围说明。
- Markdown：
  - 第一行为列标题，第二行为对齐分隔行，其后为数据行；对多行表头时合并为一行文案。
- PDF：
  - 通过 CDN 引入 `html2pdf.js`，对 `.table-wrapper` 或临时克隆节点进行导出，保留现有样式。
  - 纸张：A4 横向；页边距适中；缩放 `scale` 以在单页尽可能容纳更多列。

## 大数据量进度与性能
- 阈值判断：`rows >= 10000` 或 `rows * cols >= 10000` 即启用进度提示。
- 进度 UI：`progress-overlay`（遮罩+进度条+百分比文案）；在导出开始时显示，结束/错误时隐藏。
- 分块策略：
  - CSV/Markdown：每 `N` 行（如 500）批次拼接字符串，通过 `setTimeout/await` 让出主线程，按比例更新进度。
  - ExcelJS：批次 `worksheet.addRow()`，定期 `await Promise.resolve()` 更新进度。
  - PDF：`html2pdf()` 返回 Promise，显示“生成中”状态，若节点过大时对表格进行列宽压缩与分页标记。

## 加载状态与错误提示
- 按钮点击后立即禁用并显示 `loading` 态（旋转指示/文案）。
- `try/catch` 捕获错误，显示 `error-banner`（可关闭）。
- 完成后重置按钮状态并给出 `toast` 成功提示。

## PDF分页保证
- CSS 增加：行允许 `page-break-inside: avoid`；表头使用 `position: sticky` 的同时为导出克隆节点移除 sticky，避免分页异常。
- `html2pdf` 选项 `pagebreak: { mode: ['css','legacy'] }`，并在列宽过多时自动缩放。

## 图标与可访问性
- 切换按钮文本与 aria-label：依据当前状态显示“↔️ 指标为行”或“↕️ 日期为行”，并提供 `title` tooltip。
- 导出菜单项图标：
  - PDF：`📄` 或内联 SVG 文档图标
  - CSV：`🧾`
  - Excel：`📊`
  - Markdown：`📝`
- 键盘可访问：按钮 `tabindex=0`，`Enter/Space` 触发；菜单可用 `Esc` 关闭。

## 代码改动点（文件）
- `dashboard/index.html`：在 `section.table-section` 中新增工具栏与导出菜单结构，必要时引入第三方库 CDN（`html2pdf.js`、`exceljs`）。
- `dashboard/styles.css`：添加工具栏、按钮、下拉、tooltip、进度遮罩、fade-in 动画样式；补充移动端断点规则。
- `dashboard/app.js`：
  - 新增状态 `isTransposed` 与事件绑定。
  - 提取 `buildPivotModel`、`transposeModel`、`collectPivotData`。
  - 改造 `renderPivotTable(selectedInds)` 支持两种渲染与动画。
  - 实现 `exportToCSV/Excel/Markdown/PDF` 与进度、错误、加载反馈。

## 验证方案
- 功能回归：勾选多指标、修改起止周期，确认切换保留状态并平滑过渡。
- 导出对比：
  - CSV/Markdown 打开查看行列、编码与内容；
  - Excel 查看表头加粗/冻结；
  - PDF 逐页检查分页与样式一致性。
- 性能测试：构造 ≥1万行数据（或倍增日期/指标）验证进度提示与界面不卡顿。

## 依赖说明
- 通过 CDN 引入：
  - `html2pdf.js`（PDF）
  - `exceljs`（Excel 样式与冻结）
- 其余格式（CSV/Markdown）纯前端实现，无外部依赖。

## 交付与回滚
- 所有改动仅在 `dashboard/` 下，结构清晰易回滚；第三方库仅通过 `<script>` 标签按需加载。
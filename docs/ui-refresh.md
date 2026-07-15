# UI Refresh — 科幻战报 HUD

静态栈（`public/`）视觉升级说明。数据契约不变，仍读取 `public/data/*.json`。

## 设计原则

- **战报感**：侧栏导航 + 主壳悬浮面板 + 热点 Hero + 状态链路条
- **层次清晰**：背景网格 / 玻璃面板 / 卡片抬升三级；Hero 带呼吸光晕，主卡片用暗线轮廓区分热区
- **可读优先**：Orbitron 仅用于标题；正文 `Inter` + `Noto Sans SC`；数值 `.metric` → JetBrains Mono
- **动效友好**：尊重 `prefers-reduced-motion`（关闭 orbit / Hero 光晕 / 状态扫描 / 错误脉冲）

## Design Tokens（`public/hud.css` `:root`）

| Token | 用途 |
|-------|------|
| `--bg-base` / `--bg-panel` / `--bg-panel-strong` | 背景与面板 |
| `--accent-primary` `#50c8ff` | 主强调 / 官方倾向 |
| `--accent-secondary` `#7a62ff` | 次强调 / Hero 点缀 |
| `--accent-warm` `#f6a00c` | 社区 / 警告 |
| `--accent-error` `#ff4d6d` | 错误 |
| `--text-strong` / `--text-main` / `--text-muted` | 文字三级 |
| `--shadow-soft` / `--shadow-focus` | 悬浮与聚焦 |
| `--grid-overlay` | 背景网格 |

### 对比度速查（深色 HUD）

| 组合 | 前景 | 背景 | 用途 |
|------|------|------|------|
| CTA 主按钮 | `#07111f` | `#50c8ff` → `#7a62ff` | 刷新 / 强调按钮 |
| 正文 | `#c9d4ff` | `#040510` / panel | 说明文字 |
| 强文案 | `#f4f6ff` | panel | 标题 |
| Meta | `#a8b4e0` | panel-strong | 状态条来源/时间 |
| Metric | `#50c8ff` / `#7dd8ff` | panel | 倒计时、百分比 |

> 目标：正文与背景对比不低于常见 WCAG AA 观感；主按钮使用深字配亮 accent。

## `.metric` 强制使用场景

以下数字类 UI **必须**包 `.metric`（JetBrains Mono）：

- 活动倒计时 / 剩余时间（卡片 `remain`、Hero 描述中的数值段可选）
- 进度百分比（`pct-num`）
- 开始 / 截止时间戳（卡片脚栏）
- 状态条「最后同步」时间
- 顶栏「数据更新于」时间
- （预留）人数 / 周期 / 刷新秒数等统计数字

非数字文案、游戏名、标签名 **不要** 滥用 `.metric`。

## 组件规范

### Hero（`#heroBanner`）
热点活动横幅：图标 + 标题/描述 + CTA。`updateHero()` 优先「将截止」。背景含 `heroGlow` 呼吸光晕（约 5.5s）。

### Filter stack
- 上层：搜索 + 类型 chips（加大 padding / hover 抬升 / checked 微光）
- 下层：统计 meta + 折叠/管理/刷新

### Status（`.status--success|warning|error|loading`）
三列：`status__icon` | `status__body` | `status__meta`（左侧分隔线 + 提亮色）。

出现扫描：`.status::after` + `statusScan` **400ms**（自左向右淡出）。

### 定时全页扫描（TODO 构想）

挂在 `.app-shell.is-scanning::after`，参数草案：

```css
@keyframes hudSweep {
  from { transform: translateX(-120%); opacity: 0; }
  20%  { opacity: 0.55; }
  to   { transform: translateX(120%); opacity: 0; }
}
/* duration: 700ms; easing: cubic-bezier(0.22, 1, 0.36, 1); */
```

触发点：约每 30s 数据刷新成功后（见 `public/js/main.js` `TODO(ui)`）。实现时需同时尊重 `prefers-reduced-motion`。

### Briefing card（`.briefing-card`）
- 顶栏 ribbon：`letter-spacing: 0.04em`，单行省略防折行破坏
- 标题：`line-height: 1.3`，最多两行省略
- 外轮廓：暗色 `border` + 1px accent `outline` 明确热区
- Accent：`.card--accent-blue|violet|warm|orange|red|teal|pink`

### Sidebar
深蓝→黑渐变；激活项左侧 4px 亮条 + inset glow。

**未来计划（非遗漏）**：平板改为 **icon 精简侧栏**；当前 ≤1100 统一用抽屉 collapse，避免半成品交互。

## 响应式 / 截图

| 断点 | 行为 | 截图 |
|------|------|------|
| ≥1280 Desktop | 完整侧栏 + 壳层 | `docs/screenshots/desktop-1440.png` |
| ~900 Tablet | 侧栏抽屉；Hero CTA 下折 | `docs/screenshots/tablet-900.png` |
| 390 Mobile | 单列 Hero；筛选两列 | `docs/screenshots/mobile-390.png` |
| 414 Mobile+ | 扩展参考（iPhone 大屏） | `docs/screenshots/mobile-414.png` |

## 已知限制 / TODO

1. **平板 Icon 侧栏**：计划项，非本轮范围；现阶段抽屉即可。
2. **`hudSweep` 定时扫描**：规格已定，待接刷新钩子。
3. **无 npm build**：静态站；验证 = `python -m http.server 5173` + 浏览器。

## QA 清单

- [ ] Chrome / Edge 最新版：Hero 光晕、卡片抬升、chip hover
- [ ] Safari：`backdrop-filter` 与侧栏抽屉
- [ ] 系统「减少动态效果」开启时无持续动画
- [ ] 深色背景下主按钮字色为 `#07111f`，hover 清晰
- [ ] 长标题卡片仅两行省略，不挤压进度区
- [ ] 本地预览：`http://localhost:5173/public/`

## 预览

```bash
python -m http.server 5173
# http://localhost:5173/public/
```

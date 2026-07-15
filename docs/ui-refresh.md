# UI Refresh — 科幻战报 HUD

静态栈（`public/`）视觉升级说明。数据契约不变，仍读取 `public/data/*.json`。

## 设计原则

- **战报感**：侧栏导航 + 主壳悬浮面板 + 热点 Hero + 状态链路条
- **层次清晰**：背景网格 / 玻璃面板 / 卡片抬升三级
- **可读优先**：Orbitron 仅用于标题；正文 `Inter` + `Noto Sans SC`（思源黑体族）；数值 `.metric` → JetBrains Mono

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

## 组件规范

### Hero（`#heroBanner`）
热点活动横幅：图标 + 标题/描述 + CTA。数据由 `updateHero()` 从已加载事件中选取「将截止优先」。

### Filter stack
- 上层：搜索 + 类型 chips  
- 下层：统计 meta + 折叠/管理/刷新  

### Status（`.status--success|warning|error|loading`）
三列网格：`status__icon` | `status__body` | `status__meta`。出现时顶部光线扫描 400ms。

### Briefing card（`.briefing-card`）
- 顶栏游戏 ribbon + 类型 pill  
- 封面 + 状态徽章  
- 倒计时 / 进度刻度 / 始止时间脚栏  
- Accent：`.card--accent-blue|violet|warm|orange|red|teal|pink`

### Sidebar
深蓝→黑渐变；激活项左侧 4px 亮条 + inset glow。窄屏抽屉 + 关闭按钮。

## 响应式

| 断点 | 行为 |
|------|------|
| ≥1280 | 桌面完整布局 |
| ≤1100 | 侧栏抽屉；Hero CTA 下折 |
| ≤768 | Hero 单列；筛选两列；状态条竖向栈 |

## 已知限制 / TODO

- 平板「侧栏 Icon 模式」未做，暂用抽屉 collapse（见 `main.js` TODO 扫描线注释旁结构限制）。
- 约 30s 刷新触发 HUD 扫描线：`TODO(ui)` 于 `main.js`，待接入定时刷新钩子。
- 无 `npm run build`：本项目为静态站，验证方式为本地 `python -m http.server` + 浏览器检查。

## 预览

```bash
python -m http.server 5173
# http://localhost:5173/public/
```

截图参考：`docs/screenshots/`（desktop / tablet / mobile）。

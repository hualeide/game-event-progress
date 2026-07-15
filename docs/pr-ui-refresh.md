# PR 描述草稿 — feat/ui-refresh-static

可直接粘贴到 GitHub PR：

---

## TL;DR
将静态活动进度页升级为**科幻战报风 HUD**：侧栏导航 + 玻璃主壳 + HOT BRIEF Hero + 状态链路条 + 战报卡片。无新框架依赖，JSON schema 不变。

关键词：`HUD` · `briefing card` · `design tokens` · `static`

## 核心更新
- Design tokens / Orbitron+Inter+Noto+JetBrains / `.metric`
- Hero 热点横幅、两层筛选、状态条 BEM + 扫描线
- 战报卡片（ribbon / 刻度进度 / accent 变体）
- 文档 `docs/ui-refresh.md` + 多断点截图

## Screenshots
| Desktop | Tablet | Mobile | Mobile 414 |
|---------|--------|--------|------------|
| `docs/screenshots/desktop-1440.png` | `tablet-900.png` | `mobile-390.png` | `mobile-414.png` |

## TODO / 限制
- 平板 icon 侧栏（计划中，现用抽屉）
- 定时 `hudSweep` 扫描线（规格已写，待接刷新钩子）
- 无 npm build（静态站）

## 验证
```bash
python -m http.server 5173
# http://localhost:5173/public/
```
见 `docs/ui-refresh.md` QA 清单。

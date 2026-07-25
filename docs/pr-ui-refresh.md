# PR 描述草稿 — feat/ui-refresh-static

可直接粘贴到 GitHub PR：

---

## TL;DR
将静态活动进度页升级为**科幻战报风 HUD**：全宽玻璃主壳 + 两层筛选 + 状态链路条 + 战报卡片。无新框架依赖，JSON schema 不变。

关键词：`HUD` · `briefing card` · `design tokens` · `static`

## 核心更新
- Design tokens / Orbitron+Inter+Noto+JetBrains / `.metric`
- 移除左侧侧栏与 HOT BRIEF Hero；游戏管理走顶栏「管理」
- 两层筛选、状态条 BEM + 扫描线；空状态条不占位
- 战报卡片（ribbon / 刻度进度 / accent 变体）
- 文档 `docs/ui-refresh.md`

## TODO / 限制
- 定时 `hudSweep` 扫描线（规格已写，待接刷新钩子）
- 无 npm build（静态站）

## 验证
```bash
python -m http.server 5173
# http://localhost:5173/public/
```
见 `docs/ui-refresh.md` QA 清单。

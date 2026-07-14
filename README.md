# 活动进度

多游戏活动 / 卡池进度页：抓取官方公告与公开日历，解析起止时间，用进度卡片展示。

预览：`http://localhost:5173/public/`

---

## 快速开始

```bash
# 抓取 + 自查 + 发布到 public/data
python scripts/update.py

# 本地预览（项目根目录）
python -m http.server 5173
```

浏览器打开：http://localhost:5173/public/

---

## 日常运维（上线后必做）

### 一键更新（推荐）

```bash
python scripts/update.py
```

流水线顺序：

1. `fetch_all.py` — 抓取各游戏（单源失败不阻断）
2. `audit.py` — 自查，写 `data/audit-report.json`
3. `publish_data.py` — 同步 JSON → `public/data/`（静态站可读）
4. 写 `data/status.json` + `public/data/status.json`（前端显示「更新于」）

常用参数：

| 参数 | 说明 |
|------|------|
| `--jobs 2` | 并行抓取（不稳时用 1） |
| `--timeout 300` | 单脚本超时秒 |
| `--skip-fetch` | 只审计 + 发布 |
| `--strict` | 软警告也失败 |
| `--only fetch_hoyoverse.py` | 只跑部分脚本 |

### 自动定时

**GitHub Actions（推荐）**

1. 把仓库推到 GitHub，默认分支 `main` 或 `master`
2. 已带 [`.github/workflows/update.yml`](.github/workflows/update.yml)：每 6 小时抓取并自动 commit 数据
3. GitHub Pages：Settings → Pages → 源选 `Deploy from branch`，目录 `/public`（或用 Actions 部署 `public`）

**Windows 任务计划**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_update.ps1
```

建议每 6 小时运行一次。

**Linux cron**

```cron
0 */6 * * * cd /path/to/repo && ./scripts/run_update.sh >> data/cron.log 2>&1
```

---

## 目录

| 路径 | 用途 |
|------|------|
| `public/` | 静态站点（HTML/CSS/JS + covers + data） |
| `data/` | 抓取原始 JSON / 审计报告 |
| `scripts/update.py` | 一键流水线 |
| `scripts/fetch_*.py` | 各游戏抓取 |
| `scripts/audit.py` | 自查 |
| `scripts/publish_data.py` | 发布到 `public/data` |

前端数据路径优先 `./data/`（已发布），找不到再回退 `../data/`。

---

## 自查

```bash
python scripts/audit.py
python scripts/audit.py --strict   # CI 用
```

- 退出码 `2`：硬问题（重复标题、纯公告带时段等）
- 退出码 `1`：仅 `--strict` 时的软警告（空 pending、缺 Wiki 等）
- 报告：`data/audit-report.json`

---

## 部署检查清单

- [ ] `python scripts/update.py` 成功
- [ ] 打开 `/public/` 能看到「数据更新于 …」
- [ ] 游戏选择 / 排序 / 搜索可用
- [ ] GitHub Actions 已启用（或本机定时任务）
- [ ] Pages / CDN 指向 `public/`

---

## 数据来源说明

各游戏官方公告 API / 官网新闻 / 公开日历（如星铁跃迁日历）。估时条目会标「估时」，请以游戏内为准。

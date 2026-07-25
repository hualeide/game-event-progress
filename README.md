# 活动进度

**作用**：把多游戏正在进行的作战 / 卡池 / 网页活动，汇总成一张可静态部署的进度页。

**原理**：抓各游戏官方公告或公开日历 → 用规则解析起止时间 → 缓存封面 → 写成 JSON → 前端按游戏分行展示进度条。

**工作流**：`scripts/update.py` 一键跑完「抓取 → 自查 → 发布到 `public/data` → 写更新时间」；GitHub Actions 定时执行同一流水线。

本地预览：`http://localhost:5173/public/`

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
| `scripts/server.py` | 静态站 + 运维 API（Docker/VPS） |
| `scripts/fetch_*.py` | 各游戏抓取 |
| `scripts/audit.py` | 自查 |
| `scripts/publish_data.py` | 发布到 `public/data` |
| `Dockerfile` / `docker-compose.yml` | 容器部署 |
| `setup.ps1` / `setup.sh` | 一键本地设置 |

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

## 部署

### 方式 1 — 本地直接运行

```powershell
# 首次设置（Windows）
.\setup.ps1

# 或 Linux/macOS
# chmod +x setup.sh && ./setup.sh

# 抓取（可选）
python scripts/update.py

# 本地预览
python -m http.server 5173
# 浏览器打开 http://localhost:5173/public/
```

### 方式 2 — Docker（VPS）

```bash
docker compose up -d
# 站点: http://localhost:8080
# 健康检查: curl http://localhost:8080/api/health
# 手动抓取: curl -X POST http://localhost:8080/api/trigger-update
# 更新日志: curl http://localhost:8080/api/update-log
```

容器内默认每 6 小时跑一轮 `scripts/update.py`（可用环境变量 `UPDATE_INTERVAL_HOURS` 调整）。

### 方式 3 — GitHub Pages（静态）

1. Push 到 GitHub
2. Settings → Pages → 源选 Deploy from branch，目录 `/public`
3. Actions 工作流每 6 小时自动抓取并提交数据

### 方式 4 — Fly.io

```bash
fly launch   # 可沿用仓库内 fly.toml
fly deploy
```

### 方式 5 — Railway

连接仓库后按 `railway.json`（Dockerfile 构建）部署；健康检查路径 `/api/health`。

### 运维 API（`scripts/server.py` / Docker）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 + 最近更新时间 |
| POST | `/api/trigger-update` | 手动触发抓取（60 秒冷却） |
| GET | `/api/update-log` | 最近一次更新日志 |

本地也可直接：`python scripts/server.py`（默认 `:8080`，根目录为 `public/`）。

### 部署检查清单

- [ ] `python scripts/update.py` 成功
- [ ] 打开站点能看到数据更新时间
- [ ] 游戏选择 / 排序 / 搜索可用
- [ ] GitHub Actions 已启用，**或** Docker/本机定时任务
- [ ] Pages / CDN / 容器端口指向正确入口

---

## 数据来源说明

各游戏官方公告 API / 官网新闻 / 公开日历（如星铁跃迁日历）。估时条目会标「估时」，请以游戏内为准。

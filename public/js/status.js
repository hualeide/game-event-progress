import { $, fmtUpdated } from "./util.js";
import { allGames, state } from "./state.js";

/** @param {string} source */
export function classifySource(source) {
  const s = String(source || "").toLowerCase();
  if (!s) return "semi";
  if (/gamekee|fandom|wiki\.gg|huijiwiki|biligame\.com\/wiki|ennead\.cc/.test(s)) return "community";
  if (
    /mihoyo|hoyoverse|hypergryph|kurogame|blizzard|sunborngame|aisnogames|hrgame|yjwujian|df\.qq|bluearchive|leiting|cbjq/.test(
      s
    )
  ) {
    return "official";
  }
  if (/wiki|fandom|社区/.test(s)) return "community";
  return "semi";
}

function sourceMixBadges() {
  const kinds = new Set();
  for (const g of allGames()) {
    if (!state.enabled.includes(g.id)) continue;
    if (state.loadState[g.id] !== "ready") continue;
    const src = state.byGame[g.id]?.source || "";
    kinds.add(classifySource(src));
  }
  if (!kinds.size) {
    return `<span class="src-badge semi">混合源</span>`;
  }
  const label = { official: "官方", semi: "半官方", community: "社区" };
  return [...kinds]
    .map((k) => `<span class="src-badge ${k}">${label[k] || k}</span>`)
    .join("");
}

/** @param {{ loading?: boolean, error?: string, onRetry?: () => void }} opts */
export function renderStatusBar(opts = {}) {
  const el = $("#statusBar");
  if (!el) return;

  if (opts.loading) {
    el.innerHTML = `<div class="status status--loading">
      <div class="status__icon"><span class="spinner" aria-hidden="true"></span></div>
      <div class="status__body">
        <p class="status__title">链路同步中</p>
        <p class="status__desc">正在获取各游戏活动数据…</p>
      </div>
      <div class="status__meta"><span>来源 · —</span><time>—</time></div>
    </div>`;
    return;
  }

  if (opts.error) {
    el.innerHTML = `<div class="status status--error">
      <div class="status__icon" aria-hidden="true">!</div>
      <div class="status__body">
        <p class="status__title">数据链路异常</p>
        <p class="status__desc">${opts.error}</p>
      </div>
      <div class="status__meta">
        <button type="button" class="retry" data-status-retry>重试</button>
      </div>
    </div>`;
    const btn = el.querySelector("[data-status-retry]");
    if (btn && opts.onRetry) btn.addEventListener("click", opts.onRetry, { once: true });
    return;
  }

  const st = state.status;
  const upd = fmtUpdated(st?.updatedAt);
  const failed = st?.fetchOk === false;
  const soft = Number(st?.auditSoft || 0);
  const hard = Number(st?.auditHard || 0);
  const cls = failed || hard > 0 ? "status--warning" : "status--success";
  const sourceHint = failed ? "部分数据源失败" : "官方公告 / 公开日历";
  const timeHint = upd || "本地预览";
  const auditHint = hard || soft ? `审计 硬${hard}/软${soft}` : "";
  const msg = st?.message || "战报通道正常";

  el.innerHTML = `<div class="status ${cls}">
    <div class="status__icon"><span class="dot" aria-hidden="true"></span></div>
    <div class="status__body">
      <p class="status__title">${sourceHint}</p>
      <p class="status__desc">${msg}${auditHint ? ` · ${auditHint}` : ""}</p>
      <div class="status-badges">${sourceMixBadges()}</div>
    </div>
    <div class="status__meta">
      <span>来源 · 混合</span>
      <time class="metric" title="${st?.updatedAt || ""}">${timeHint}</time>
    </div>
  </div>`;
}

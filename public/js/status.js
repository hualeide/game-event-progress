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
    el.innerHTML = `<div class="status loading"><span class="spinner" aria-hidden="true"></span>正在获取数据…</div>`;
    return;
  }

  if (opts.error) {
    el.innerHTML = `<div class="status error">
      <span aria-hidden="true">!</span>
      <span>${opts.error}</span>
      <button type="button" class="retry" data-status-retry>重试</button>
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
  const cls = failed || hard > 0 ? "warn" : "success";
  const sourceHint = failed ? "部分数据源失败" : "官方公告 / 公开日历";
  const timeHint = upd ? `最后同步 ${upd}` : "尚未写入 status.json（本地预览）";
  const auditHint = hard || soft ? ` · 审计 硬${hard}/软${soft}` : "";
  const msg = st?.message ? ` · ${st.message}` : "";

  el.innerHTML = `<div class="status ${cls}">
    <span class="dot" aria-hidden="true"></span>
    <span>来源：${sourceHint} · ${timeHint}${auditHint}${msg}</span>
    <span class="status-badges">${sourceMixBadges()}</span>
  </div>`;
}

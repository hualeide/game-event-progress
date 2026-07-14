const $ = (sel) => document.querySelector(sel);

/** 静态站优先读 public/data；本地未发布时回退 ../data */
const DATA_BASES = ["./data/", "../data/"];

function dataUrl(file) {
  return DATA_BASES[0] + file;
}

/** 内置游戏（有 dataUrl 的已接数据源；pending 可稍后刷新接入） */
const BUILTIN_GAMES = [
  { id: "arknights", name: "明日方舟", en: "ARKNIGHTS", icon: "./icons/arknights.png", dataUrl: dataUrl("events.json"), accent: "ark" },
  { id: "endfield", name: "终末地", en: "ENDFIELD", icon: "./icons/endfield.png", dataUrl: dataUrl("endfield.json"), accent: "ef" },
  { id: "bluearchive", name: "蔚蓝档案", en: "BLUE ARCHIVE", icon: "./icons/bluearchive.png", dataUrl: dataUrl("bluearchive.json"), accent: "ba" },
  { id: "genshin", name: "原神", en: "GENSHIN", icon: "./icons/genshin.png", dataUrl: dataUrl("genshin.json"), accent: "gi" },
  { id: "starrail", name: "崩坏：星穹铁道", en: "STAR RAIL", icon: "./icons/starrail.png", dataUrl: dataUrl("starrail.json"), accent: "sr" },
  { id: "zzz", name: "绝区零", en: "ZZZ", icon: "./icons/zzz.png", dataUrl: dataUrl("zzz.json"), accent: "zz" },
  { id: "wuwa", name: "鸣潮", en: "WUTHERING WAVES", icon: "./icons/wuwa.png", dataUrl: dataUrl("wuwa.json"), accent: "ww" },
  { id: "azurlane", name: "碧蓝航线", en: "AZUR LANE", icon: "./icons/azurlane.png", dataUrl: dataUrl("azurlane.json"), accent: "al" },
  { id: "nikke", name: "胜利女神：NIKKE", en: "NIKKE", icon: "./icons/nikke.png", dataUrl: dataUrl("nikke.json"), accent: "nikke" },
  { id: "reverse1999", name: "重返未来：1999", en: "REVERSE 1999", icon: "./icons/reverse1999.png", dataUrl: dataUrl("reverse1999.json"), accent: "r1999" },
  { id: "ptn", name: "无期迷途", en: "PATH TO NOWHERE", icon: "./icons/ptn.png", dataUrl: dataUrl("ptn.json"), accent: "ptn" },
  { id: "snowbreak", name: "尘白禁区", en: "SNOWBREAK", icon: "./icons/snowbreak.png", dataUrl: dataUrl("snowbreak.json"), accent: "snow" },
  { id: "gfl2", name: "少女前线2：追放", en: "GFL2", icon: "./icons/gfl2.png", dataUrl: dataUrl("gfl2.json"), accent: "gfl2" },
  { id: "hearthstone", name: "炉石传说", en: "HEARTHSTONE", icon: "./icons/hearthstone.png", dataUrl: dataUrl("hearthstone.json"), accent: "hs" },
  { id: "pvz2", name: "植物大战僵尸2", en: "PVZ2 CN", icon: "./icons/pvz2.png", dataUrl: dataUrl("pvz2.json"), accent: "pvz" },
  { id: "naraka", name: "永劫无间", en: "NARAKA", icon: "./icons/naraka.png", dataUrl: dataUrl("naraka.json"), accent: "naraka" },
  { id: "delta", name: "三角洲行动", en: "DELTA FORCE", icon: "./icons/delta.png", dataUrl: dataUrl("delta.json"), accent: "delta" },
];

const DEFAULT_ENABLED = BUILTIN_GAMES.map((g) => g.id);

/** 详情页用：eventId → { game, ev } */
const eventIndex = new Map();

/** Wiki / 自动化元数据 */
const gamesMeta = { byId: {} };

const CAT_ORDER = ["combat", "gacha", "web", "event"];
const DEFAULT_CATS = { combat: true, gacha: true, web: true, event: false };

function loadCustomGames() {
  try {
    return JSON.parse(localStorage.getItem("dock.custom") || "[]") || [];
  } catch {
    return [];
  }
}

function saveCustomGames(list) {
  localStorage.setItem("dock.custom", JSON.stringify(list));
}

function metaFor(game) {
  return gamesMeta.byId[game.id] || {};
}

function toolsFor(game) {
  if (game.tools?.length) return game.tools;
  return (metaFor(game).tools || []).filter((t) => t?.url && !/mirrorchyan/i.test(t.url));
}

function wikiFor(game) {
  if (game.wiki?.url) return game.wiki;
  return metaFor(game).wiki || null;
}

function allGames() {
  const custom = loadCustomGames().map((g) => ({
    ...g,
    accent: "custom",
    custom: true,
    en: g.en || "CUSTOM",
    icon: g.icon || "./icons/custom.svg",
    tools: g.tools || [],
    wiki: g.wiki || null,
  }));
  return [
    ...BUILTIN_GAMES.map((g) => ({
      ...g,
      tools: toolsFor(g),
      wiki: wikiFor(g),
    })),
    ...custom,
  ];
}

async function loadGamesMeta() {
  const hit = await fetchFirstOk(DATA_BASES.map((b) => b + "games-meta.json"));
  if (!hit) return;
  try {
    const data = await hit.res.json();
    gamesMeta.byId = data.games || {};
  } catch {
    /* ignore */
  }
}

async function loadStatus() {
  const hit = await fetchFirstOk(DATA_BASES.map((b) => b + "status.json"));
  if (!hit) return;
  try {
    state.status = await hit.res.json();
  } catch {
    state.status = null;
  }
}

function fmtUpdated(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${m}/${day} ${h}:${min}`;
}

function endingSoon(ev) {
  if (!ev?.end) return false;
  const end = new Date(ev.end).getTime();
  const now = Date.now();
  const left = end - now;
  return left > 0 && left <= 48 * 3600 * 1000;
}

function toolsHtml(game, { compact = false } = {}) {
  const wiki = wikiFor(game);
  const tools = toolsFor(game);
  const parts = [];
  if (wiki?.url) {
    parts.push(
      `<a class="tool-link wiki" href="${wiki.url}" target="_blank" rel="noopener" title="Wiki" data-tool>${wiki.name || "Wiki"}</a>`
    );
  }
  tools.slice(0, compact ? 2 : 5).forEach((t) => {
    parts.push(
      `<a class="tool-link" href="${t.url}" target="_blank" rel="noopener" title="${t.desc || t.name}" data-tool>${t.name}</a>`
    );
  });
  if (!parts.length) return "";
  return `<div class="tool-row ${compact ? "compact" : ""}" data-tools>${parts.join("")}</div>`;
}

function migrateCats(raw) {
  const cats = { ...DEFAULT_CATS, ...(raw || {}) };
  if (raw && raw.other != null && raw.event == null) {
    cats.event = Boolean(raw.other);
  }
  delete cats.other;
  // 保证新分类存在
  for (const k of CAT_ORDER) {
    if (cats[k] == null) cats[k] = DEFAULT_CATS[k];
  }
  // v2：默认打开卡池（旧缓存曾默认关）
  const ver = Number(localStorage.getItem("dock.catsVer") || 0);
  if (ver < 2) {
    cats.gacha = true;
    localStorage.setItem("dock.catsVer", "2");
  }
  return cats;
}

const state = {
  byGame: {},
  collapsed: JSON.parse(localStorage.getItem("dock.collapsed") || "{}"),
  enabled: JSON.parse(localStorage.getItem("dock.enabled") || "null") || DEFAULT_ENABLED,
  cats: migrateCats(JSON.parse(localStorage.getItem("dock.cats") || "null")),
  hideEmpty: localStorage.getItem("dock.hideEmpty") !== "0",
  query: "",
  status: null,
};

async function fetchFirstOk(paths) {
  for (const p of paths) {
    try {
      const res = await fetch(p + (p.includes("?") ? "&" : "?") + "t=" + Date.now());
      if (res.ok) return { res, path: p };
    } catch {
      /* try next */
    }
  }
  return null;
}

function fmtDate(iso) {
  if (!iso) return "?";
  const d = new Date(iso);
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${m}/${day} ${h}:${min}`;
}

function shortName(ev) {
  const title = (ev.title || "").replace(/^预告·/, "").trim();
  if (title && title.length <= 28) return title;
  const raw = (ev.header || title || "").replace(/^预告·/, "");
  const m = raw.match(/[「【\[]([^」】\]]+)[」】\]]/);
  if (m) return m[1];
  // header 若把说明拼进来，只取 · 前主名
  const head = raw.split(/[·・]/)[0].trim();
  if (head && head.length <= 28) return head;
  return raw
    .replace(/活动即将开启|限时活动|故事集|即将开启|后续|预告·|预计.+开启|祈愿|跃迁|调频|唤取/g, "")
    .replace(/[【】\[\]\s]+/g, " ")
    .trim()
    .slice(0, 28);
}

function eventCategory(ev) {
  const t = `${ev.title || ""} ${ev.header || ""} ${ev.summary || ""} ${ev.primaryLabel || ""}`;
  // 标题识别优先：旧数据可能仍标成 event
  if (ev.webUrl || /网页活动|H5|新网页活动|浏览器|专题页|外链活动|官网活动|web\s*event/i.test(t)) {
    return "web";
  }
  if (CAT_ORDER.includes(ev.category)) return ev.category;
  if (ev.category === "other") return "event";
  if (/寻访|卡池|祈愿|跃迁|调频|招募|UP|特选|唤取|建造|共鸣/.test(t)) return "gacha";
  if (/签到|登录|维护|兑换|商店|特卖|申领|创作|征集|时装|涂装|皮肤|邮件|优化|修复|拍照|委托|回礼|直播/.test(t)) {
    return "event";
  }
  return "combat";
}

/** 可外跳的链接（排除游戏内 uniwebview） */
function jumpUrl(ev) {
  const u = (ev.webUrl || ev.link || "").trim();
  if (!u) return "";
  if (/^uniwebview:/i.test(u)) return "";
  if (/^https?:\/\//i.test(u) || u.startsWith("//")) return u.startsWith("//") ? `https:${u}` : u;
  return "";
}

function isWebEvent(ev) {
  return eventCategory(ev) === "web" || Boolean(ev.webUrl);
}

function liveStats(ev) {
  const start = ev.start ? new Date(ev.start) : null;
  const end = ev.end ? new Date(ev.end) : null;
  const now = new Date();
  if (!start || !end || !(end > start)) {
    return { status: "未知", kind: "live", remain: "?", pct: 0, tip: "" };
  }
  const totalMs = end - start;
  const totalDays = totalMs / 86400000;

  if (now < start) {
    const until = start - now;
    const days = Math.floor(until / 86400000);
    const hours = Math.floor((until % 86400000) / 3600000);
    return {
      status: "即将开始",
      kind: "preview",
      remain: days > 0 ? `${days}天后` : hours > 0 ? `${hours}小时后` : "即将开始",
      pct: 0,
      tip: ev.fuzzy
        ? `预告（估时）· 约 ${fmtDate(ev.start)} 前后`
        : `还未开始 · ${fmtDate(ev.start)} 开启`,
    };
  }
  if (now >= end) {
    return { status: "已结束", kind: "done", remain: "已结束", pct: 100, tip: "已结束" };
  }
  const elapsedMs = now - start;
  const remainMs = end - now;
  const pct = Math.max(0, Math.min(100, (elapsedMs / totalMs) * 100));
  const remainDays = Math.floor(remainMs / 86400000);
  const remainHours = Math.floor((remainMs % 86400000) / 3600000);
  const elapsedDays = elapsedMs / 86400000;
  return {
    status: "进行中",
    kind: "live",
    remain:
      remainDays > 0
        ? remainHours
          ? `${remainDays}天${remainHours}时`
          : `${remainDays}天`
        : remainHours > 0
          ? `${remainHours}小时`
          : "将结束",
    pct,
    tip: `已过 ${elapsedDays.toFixed(1)} 天 / 共 ${totalDays.toFixed(1)} 天`,
  };
}

function catLabel(cat) {
  return (
    {
      combat: "作战",
      gacha: "卡池",
      web: "网页",
      event: "活动",
    }[cat] || "活动"
  );
}

function splitEvents(events) {
  const live = [];
  const preview = [];
  for (const e of events || []) {
    if (!e.hasSchedule) continue;
    const cat = eventCategory(e);
    if (!state.cats[cat]) continue;
    const s = liveStats(e);
    if (s.status === "进行中") live.push(e);
    else if (s.status === "即将开始") preview.push(e);
  }
  // 进行中：将截止优先；预告：开始时间近的优先
  live.sort((a, b) => new Date(a.end) - new Date(b.end));
  preview.sort((a, b) => new Date(a.start) - new Date(b.start));
  return { live, preview };
}

/** 按封面真实比例收紧卡片，避免超宽/方图留大块空白 */
function adaptCover(img) {
  const cover = img?.closest?.(".cover");
  const card = img?.closest?.(".card");
  if (!cover || !card || !img.naturalWidth) return;
  const r = img.naturalWidth / img.naturalHeight;
  let kind = "std";
  let ar = "16 / 9";
  if (r >= 2.35) {
    kind = "wide";
    ar = `${r.toFixed(3)} / 1`;
  } else if (r <= 1.15) {
    kind = "square";
    ar = "1 / 1";
  } else if (r < 1.45) {
    kind = "tall";
    ar = `${r.toFixed(3)} / 1`;
  }
  card.dataset.ratio = kind;
  cover.style.aspectRatio = ar;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function normKey(s) {
  return String(s || "")
    .replace(/[\s「」『』【】\[\]（）()·・\-—_/|/\\.,，。！!？?：:；;“”‘’"']+/g, "")
    .toLowerCase();
}

/** 真正有内容的原文；标题复读不算 */
function bodyText(ev) {
  const aliases = [ev.title, ev.header, shortName(ev), ev.primaryLabel]
    .map(normKey)
    .filter((a) => a.length >= 2);
  for (const raw of [ev.body, ev.text, ev.textPreview, ev.summary]) {
    if (!raw) continue;
    const trimmed = String(raw).trim();
    if (!trimmed) continue;
    const oneLine = trimmed.replace(/\s+/g, " ");
    const key = normKey(oneLine);
    if (!key) continue;
    if (
      aliases.some(
        (a) => key === a || (a.length >= 4 && key.length <= a.length + 8 && (key.includes(a) || a.includes(key)))
      )
    ) {
      continue;
    }
    if (oneLine.length < 28 && !/活动时间|开放时间|说明|奖励|参加|关卡/.test(oneLine)) continue;
    return trimmed;
  }
  return "";
}

function cardSubline(ev, live) {
  const label = (ev.primaryLabel || "").trim();
  if (label) return label;
  if (live.tip) return live.tip;
  const body = bodyText(ev);
  if (body) return body.replace(/\s+/g, " ").trim().slice(0, 36);
  return "";
}

function cardHtml(game, ev) {
  const live = liveStats(ev);
  const name = shortName(ev);
  const src = ev.banner || "";
  const cat = eventCategory(ev);
  const stateText =
    live.status === "即将开始" ? "预告" : live.status === "进行中" ? "进行中" : "已结束";
  const kindClass = stateText === "预告" ? "preview" : stateText === "进行中" ? "live" : "done";
  const eid = String(ev.id || `${game.id}-${name}`);
  eventIndex.set(eid, { game, ev });
  const sub = cardSubline(ev, live);
  const jump = jumpUrl(ev);
  const web = isWebEvent(ev);
  const coverInner = src
    ? `<img class="cover-blur" src="${src}" alt="" aria-hidden="true" loading="lazy" />
       <img class="cover-img" src="${src}" alt="${name}" loading="lazy"
         onload="adaptCover(this)"
         onerror="const c=this.parentElement;const b=this.previousElementSibling;if(b)b.remove();this.remove();if(c)c.classList.add('cover-fallback');" />`
    : "";
  const jumpBtn =
    jump && web
      ? `<a class="jump-btn" href="${jump}" target="_blank" rel="noopener" data-jump title="打开网页活动">打开</a>`
      : jump
        ? `<a class="jump-btn muted" href="${jump}" target="_blank" rel="noopener" data-jump title="打开链接">链接</a>`
        : "";

  const fuzzy = ev.fuzzy ? `<span class="badge fuzzy">估时</span>` : "";
  return `
  <article class="card ${kindClass === "preview" ? "preview" : ""} ${web ? "is-web" : ""} ${endingSoon(ev) ? "is-soon" : ""}" title="${live.tip || ""} · 点击查看详情"
    data-event-id="${eid}" data-game-id="${game.id}" data-cat="${cat}" tabindex="0" role="button">
    <div class="cover ${src ? "" : "cover-fallback"}">
      ${coverInner}
      <span class="badge ${kindClass}">${stateText}</span>
      <span class="badge-cat cat-${cat}">${catLabel(cat)}</span>
      ${fuzzy}
      ${jumpBtn}
    </div>
    <div class="bar">
      <p class="bar-title">${name}${endingSoon(ev) ? `<em class="soon-tag">将截止</em>` : ""}</p>
      ${sub ? `<p class="bar-sub">${sub}</p>` : ""}
      <div class="remain ${kindClass} ${endingSoon(ev) ? "soon" : ""}">
        ${live.remain}
        <small>${endingSoon(ev) ? "将截止" : stateText}</small>
      </div>
      <div class="mid">
        <div class="dates">
          <span><em>起</em>${fmtDate(ev.start)}</span>
          <span><em>止</em>${fmtDate(ev.end)}</span>
        </div>
        <div class="track">
          <div class="fill" style="width:${live.pct.toFixed(1)}%"></div>
        </div>
        <div class="pct-row">
          <span>${live.pct.toFixed(0)}%</span>
          <span>${kindClass === "live" ? "已过时段" : kindClass === "preview" ? "未开始" : "已结束"}</span>
        </div>
      </div>
    </div>
  </article>`;
}

function gamesById() {
  return new Map(allGames().map((g) => [g.id, g]));
}

function gameVisibleCount(game) {
  const events = matchQueryEvents(state.byGame[game.id]?.events || game.events || []);
  const { live, preview } = splitEvents(events);
  return live.length + preview.length;
}

/** 主列表顺序 = 勾选顺序（state.enabled） */
function visibleGames() {
  const map = gamesById();
  let list = state.enabled.map((id) => map.get(id)).filter(Boolean);
  const q = state.query.trim().toLowerCase();
  if (q) {
    list = list.filter((g) => {
      const blob = `${g.name} ${g.en} ${g.id}`.toLowerCase();
      if (blob.includes(q)) return true;
      const events = state.byGame[g.id]?.events || g.events || [];
      return events.some((ev) => {
        const t = `${ev.title || ""} ${ev.header || ""}`.toLowerCase();
        return t.includes(q);
      });
    });
  }
  if (state.hideEmpty) {
    list = list.filter((g) => gameVisibleCount(g) > 0 || state.byGame[g.id]?.pending);
  }
  return list;
}

function matchQueryEvents(events) {
  const q = state.query.trim().toLowerCase();
  if (!q) return events;
  return events.filter((ev) => {
    const t = `${ev.title || ""} ${ev.header || ""}`.toLowerCase();
    return t.includes(q);
  });
}

/** 选择面板：已选在前（按顺序），未选在后 */
function gamesForPicker() {
  const all = allGames();
  const map = new Map(all.map((g) => [g.id, g]));
  const on = state.enabled.map((id) => map.get(id)).filter(Boolean);
  const off = all.filter((g) => !state.enabled.includes(g.id));
  return [...on, ...off];
}

function moveEnabled(id, dir) {
  const i = state.enabled.indexOf(id);
  if (i < 0) return;
  const j = i + dir;
  if (j < 0 || j >= state.enabled.length) return;
  const next = state.enabled.slice();
  [next[i], next[j]] = [next[j], next[i]];
  state.enabled = next;
  persist();
  renderPicker();
  render();
}

function gameRowHtml(game, payload) {
  const collapsed = Boolean(state.collapsed[game.id]);
  const events = matchQueryEvents(payload?.events || game.events || []);
  const { live, preview } = splitEvents(events);
  const total = live.length + preview.length;
  const ready = Boolean(game.dataUrl || game.custom) && Array.isArray(events);
  const emptyHint = payload?.pending
    ? "数据源待接入（可自定义添加活动）"
    : "当前筛选下暂无活动";

  let body;
  if (payload?.pending && total === 0) {
    body = `<p class="game-empty">${emptyHint}</p>`;
  } else if (total === 0) {
    body = `<p class="game-empty">${emptyHint}</p>`;
  } else {
    body = `<div class="game-track">${[...live, ...preview].map((ev) => cardHtml(game, ev)).join("")}</div>`;
  }

  return `
  <section class="game-row ${collapsed ? "collapsed" : ""}" data-game="${game.id}" data-accent="${game.accent || ""}">
    <div class="game-head">
      <button type="button" class="game-bar" data-toggle="${game.id}" aria-expanded="${!collapsed}">
        <img class="game-icon" src="${game.icon}" alt="${game.name}" onerror="this.src='./icons/custom.svg'" />
        <div class="game-name">${game.name}<small>${game.en}</small></div>
        <span class="game-count ${total === 0 ? "is-zero" : ""}">${total}</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      ${toolsHtml(game, { compact: true })}
    </div>
    <div class="game-body">
      <div class="game-body-inner">${body}</div>
    </div>
  </section>`;
}

function accentColor(gameId) {
  const row = document.querySelector(`.game-row[data-game="${gameId}"]`);
  if (row) {
    const v = getComputedStyle(row).getPropertyValue("--g-accent").trim();
    if (v) return v;
  }
  return "#f0c41a";
}

function openDetail(gameId, eventId) {
  const hit = eventIndex.get(String(eventId));
  if (!hit) return;
  const { game, ev } = hit;
  const live = liveStats(ev);
  const cat = eventCategory(ev);
  const stateText =
    live.status === "即将开始" ? "预告" : live.status === "进行中" ? "进行中" : live.status;
  const kindClass = stateText === "预告" ? "preview" : stateText === "进行中" ? "live" : "done";
  const name = shortName(ev);
  const panel = $("#detail");
  panel.style.setProperty("--detail-accent", accentColor(gameId || game.id));
  $("#detailGame").textContent = `${game.name} · ${game.en}`;
  $("#detailTitle").textContent = name;
  $("#detailTags").innerHTML = `
    <span class="${kindClass}">${stateText}</span>
    <span>${catLabel(cat)}</span>
    ${ev.fuzzy ? "<span>估时</span>" : ""}`;
  $("#detailBanner").innerHTML = ev.banner
    ? `<img src="${ev.banner}" alt="${name}" />`
    : `<div class="cover-fallback" style="height:100%"></div>`;

  const ranges = (ev.allRanges || [])
    .slice(0, 8)
    .map((r) => `<li><b>${r.label || "时段"}</b> ${fmtDate(r.start)} → ${fmtDate(r.end)}</li>`)
    .join("");
  const days = ev.days || {};
  const body = bodyText(ev);
  const bodyHtml = body
    ? `<div class="detail-block"><h3>原文</h3><p class="origin-text">${escapeHtml(body).replace(/\n/g, "<br>")}</p></div>`
    : "";
  $("#detailBody").innerHTML = `
    <div class="detail-meta">
      <div><b>开始</b><span>${fmtDate(ev.start)}</span></div>
      <div><b>结束</b><span>${fmtDate(ev.end)}</span></div>
      <div><b>剩余</b><span>${live.remain}</span></div>
      <div><b>进度</b><span>${live.pct.toFixed(1)}%</span></div>
    </div>
    <div class="detail-progress" title="${live.tip || ""}"><i style="width:${live.pct.toFixed(1)}%"></i></div>
    ${
      days.totalDays != null
        ? `<p class="detail-days">已过 ${days.elapsedDays ?? "?"} / 共 ${days.totalDays} 天 · 剩 ${days.remainDays ?? "?"} 天</p>`
        : ""
    }
    ${bodyHtml}
    ${
      ranges
        ? `<div class="detail-block"><h3>更多时段</h3><ul>${ranges}</ul></div>`
        : ""
    }`;

  const jump = jumpUrl(ev);
  const wiki = wikiFor(game);
  const tools = toolsFor(game);
  const primaryLabel = isWebEvent(ev) ? "打开网页活动" : "打开链接";
  const wikiBtn = wiki?.url
    ? `<a class="ghost" href="${wiki.url}" target="_blank" rel="noopener">Wiki</a>`
    : "";
  const toolBtns = tools
    .map(
      (t) =>
        `<a class="ghost" href="${t.url}" target="_blank" rel="noopener" title="${t.desc || ""}">${t.name}</a>`
    )
    .join("");
  $("#detailFoot").innerHTML = `
    ${jump ? `<a class="primary" href="${jump}" target="_blank" rel="noopener">${primaryLabel}</a>` : ""}
    ${wikiBtn}
    ${toolBtns}
    <button type="button" class="ghost" data-close-detail>返回</button>`;

  if (wiki?.url || tools.length) {
    const block = document.createElement("div");
    block.className = "detail-block";
    const wikiHtml = wiki?.url
      ? `<a class="tool-link wiki" href="${wiki.url}" target="_blank" rel="noopener">${wiki.name || "Wiki"}<small>资料站</small></a>`
      : "";
    const toolsHtmlInner = tools
      .map(
        (t) =>
          `<a class="tool-link" href="${t.url}" target="_blank" rel="noopener" title="${t.desc || t.name}">${t.name}<small>${t.desc || ""}</small></a>`
      )
      .join("");
    block.innerHTML = `<h3>相关链接</h3><div class="tool-row">${wikiHtml}${toolsHtmlInner}</div>`;
    $("#detailBody").appendChild(block);
  }

  panel.classList.remove("hidden");
  panel.setAttribute("aria-hidden", "false");
  const hash = `#/event/${encodeURIComponent(game.id)}/${encodeURIComponent(eventId)}`;
  if (location.hash !== hash) history.replaceState(null, "", hash);
}

function closeDetail() {
  const panel = $("#detail");
  panel.classList.add("hidden");
  panel.setAttribute("aria-hidden", "true");
  if (location.hash.startsWith("#/event/")) {
    history.replaceState(null, "", location.pathname + location.search);
  }
}

function tryOpenFromHash() {
  const m = location.hash.match(/^#\/event\/([^/]+)\/(.+)$/);
  if (!m) return;
  const gameId = decodeURIComponent(m[1]);
  const eventId = decodeURIComponent(m[2]);
  if (eventIndex.has(eventId)) openDetail(gameId, eventId);
}

function persist() {
  localStorage.setItem("dock.collapsed", JSON.stringify(state.collapsed));
  localStorage.setItem("dock.enabled", JSON.stringify(state.enabled));
  localStorage.setItem("dock.cats", JSON.stringify(state.cats));
  localStorage.setItem("dock.hideEmpty", state.hideEmpty ? "1" : "0");
}

function bindCardHover() {
  $("#games").querySelectorAll(".card").forEach((card) => {
    card.addEventListener("pointerenter", () => card.classList.add("is-hot"));
    card.addEventListener("pointerleave", () => card.classList.remove("is-hot"));
  });
}

function applyFilterUI() {
  document.querySelectorAll("#filters [data-cat]").forEach((input) => {
    input.checked = Boolean(state.cats[input.dataset.cat]);
  });
  const hide = $("#hideEmpty");
  if (hide) hide.checked = Boolean(state.hideEmpty);
}

function renderSkeleton() {
  const root = $("#games");
  if (!root) return;
  root.innerHTML = Array.from({ length: 4 }, (_, i) => `
    <section class="game-row skeleton" style="--delay:${i * 0.06}s">
      <div class="game-head"><div class="sk sk-icon"></div><div class="sk sk-line"></div></div>
      <div class="game-body"><div class="game-body-inner"><div class="game-track">
        <div class="sk sk-card"></div><div class="sk sk-card"></div><div class="sk sk-card"></div>
      </div></div></div>
    </section>`).join("");
}

function renderPicker() {
  const root = $("#gamePicker");
  const games = gamesForPicker();
  const en = state.enabled;
  root.innerHTML = `
    <div class="picker-bar">
      <span class="picker-hint">勾选显示 · ↑↓ 调整主列表顺序</span>
      <span class="picker-actions">
        <button type="button" class="linkish" data-pick-all>全选</button>
        <button type="button" class="linkish" data-pick-none>最少保留1个</button>
      </span>
    </div>
    <div class="picker-grid">
      ${games
        .map((g) => {
          const on = en.includes(g.id);
          const idx = en.indexOf(g.id);
          const ord =
            on
              ? `<span class="pick-ord" title="显示顺序 ${idx + 1}">
                  <button type="button" class="ord-btn" data-move="up" data-game="${g.id}" ${idx === 0 ? "disabled" : ""} aria-label="上移">↑</button>
                  <button type="button" class="ord-btn" data-move="down" data-game="${g.id}" ${idx === en.length - 1 ? "disabled" : ""} aria-label="下移">↓</button>
                </span>`
              : "";
          return `
        <label class="pick-item ${on ? "is-on" : ""}">
          <input type="checkbox" data-game="${g.id}" ${on ? "checked" : ""} />
          <img src="${g.icon}" alt="" onerror="this.src='./icons/custom.svg'" />
          <span class="pick-name">${g.name}</span>
          ${ord}
          ${g.custom ? `<button type="button" class="rm" data-rm="${g.id}" title="删除自定义">删</button>` : ""}
        </label>`;
        })
        .join("")}
    </div>
    <form class="custom-add" id="customAdd">
      <input name="name" placeholder="自定义游戏名" required maxlength="20" />
      <input name="icon" placeholder="图标 URL（可空）" maxlength="300" />
      <button type="submit" class="btn">添加游戏</button>
    </form>
    <form class="custom-add event-add" id="customEventAdd">
      <select name="gameId" required>
        <option value="">选择自定义游戏…</option>
        ${loadCustomGames()
          .map((g) => `<option value="${g.id}">${g.name}</option>`)
          .join("")}
      </select>
      <input name="title" placeholder="活动名" required maxlength="40" />
      <input name="start" type="datetime-local" required title="开始" />
      <input name="end" type="datetime-local" required title="结束" />
      <button type="submit" class="btn ghost">加活动</button>
    </form>`;
}

function render() {
  eventIndex.clear();
  const games = visibleGames();
  $("#games").innerHTML = games.map((g) => gameRowHtml(g, state.byGame[g.id])).join("");
  bindCardHover();
  // 缓存图可能已 complete，onload 不会再触发
  $("#games").querySelectorAll(".cover-img").forEach((img) => {
    if (img.complete && img.naturalWidth) adaptCover(img);
  });

  let liveN = 0;
  let prevN = 0;
  let fuzzyN = 0;
  let soonN = 0;
  for (const g of games) {
    const events = matchQueryEvents(state.byGame[g.id]?.events || g.events || []);
    const { live, preview } = splitEvents(events);
    liveN += live.length;
    prevN += preview.length;
    const shown = [...live, ...preview];
    fuzzyN += shown.filter((e) => e.fuzzy).length;
    soonN += shown.filter((e) => endingSoon(e)).length;
  }
  const catHint = CAT_ORDER.filter((k) => state.cats[k])
    .map((k) => catLabel(k))
    .join("+");
  const upd = fmtUpdated(state.status?.updatedAt);
  const parts = [
    catHint || "无筛选",
    `进行中 ${liveN}`,
    `预告 ${prevN}`,
  ];
  if (soonN) parts.push(将截止 );
  if (fuzzyN) parts.push(`估时 ${fuzzyN}`);
  if (upd) parts.push(`更新 ${upd}`);
  if (state.query.trim()) parts.unshift(`搜「${state.query.trim()}」`);
  $("#meta").textContent = parts.join(" · ");
  const updatedEl = $("#updatedAt");
  if (updatedEl) {
    if (!upd) updatedEl.textContent = "本地预览";
    else if (state.status?.fetchOk === false)
      updatedEl.textContent = `数据更新于 ${upd} · 部分源失败`;
    else updatedEl.textContent = `数据更新于 ${upd}`;
  }
  const emptyEl = $("#empty");
  if (emptyEl) {
    emptyEl.textContent = state.query.trim()
      ? "没有匹配的游戏或活动"
      : games.length === 0
        ? "请先在「游戏」里勾选要显示的游戏"
        : "当前筛选下没有活动";
    emptyEl.classList.toggle("hidden", liveN + prevN > 0 && games.length > 0);
    if (games.length === 0) emptyEl.classList.remove("hidden");
    else if (liveN + prevN === 0) emptyEl.classList.remove("hidden");
    else emptyEl.classList.add("hidden");
  }
  tryOpenFromHash();
}

async function loadGame(game) {
  if (game.custom) {
    state.byGame[game.id] = { events: game.events || [], pending: false };
    return;
  }
  if (!game.dataUrl) {
    state.byGame[game.id] = { events: [], pending: true };
    return;
  }
  const file = game.dataUrl.split("/").pop();
  const hit = await fetchFirstOk(DATA_BASES.map((b) => b + file));
  if (!hit) {
    state.byGame[game.id] = { events: [], pending: true };
    return;
  }
  try {
    state.byGame[game.id] = await hit.res.json();
  } catch {
    state.byGame[game.id] = { events: [], pending: true };
  }
}

async function loadAll() {
  $("#meta").textContent = "加载中…";
  document.body.classList.add("is-loading");
  renderSkeleton();
  await Promise.all([loadGamesMeta(), loadStatus()]);
  await Promise.all(allGames().map(loadGame));
  document.body.classList.remove("is-loading");
  render();
}

$("#games").addEventListener("click", (e) => {
  if (e.target.closest("[data-tool], [data-tools] a, [data-jump]")) return;
  const card = e.target.closest("[data-event-id]");
  if (card) {
    openDetail(card.dataset.gameId, card.dataset.eventId);
    return;
  }
  const btn = e.target.closest("[data-toggle]");
  if (!btn) return;
  const id = btn.dataset.toggle;
  state.collapsed[id] = !state.collapsed[id];
  persist();
  const row = btn.closest(".game-row");
  row.classList.toggle("collapsed", state.collapsed[id]);
  btn.setAttribute("aria-expanded", String(!state.collapsed[id]));
});

$("#games").addEventListener("keydown", (e) => {
  if (e.key !== "Enter" && e.key !== " ") return;
  const card = e.target.closest("[data-event-id]");
  if (!card) return;
  e.preventDefault();
  openDetail(card.dataset.gameId, card.dataset.eventId);
});

$("#detail").addEventListener("click", (e) => {
  if (e.target.closest("[data-close-detail]")) closeDetail();
});

window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("#detail").classList.contains("hidden")) closeDetail();
  // Ctrl/Cmd+K 聚焦搜索
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    const search = $("#search");
    if (!search) return;
    e.preventDefault();
    search.focus();
    search.select();
  }
});

window.addEventListener("hashchange", () => {
  if (location.hash.startsWith("#/event/")) tryOpenFromHash();
  else if (!$("#detail").classList.contains("hidden")) {
    $("#detail").classList.add("hidden");
    $("#detail").setAttribute("aria-hidden", "true");
  }
});

$("#filters").addEventListener("change", (e) => {
  if (e.target.id === "hideEmpty") {
    state.hideEmpty = e.target.checked;
    persist();
    render();
    return;
  }
  const input = e.target.closest("[data-cat]");
  if (!input) return;
  state.cats[input.dataset.cat] = input.checked;
  if (!CAT_ORDER.some((k) => state.cats[k])) {
    state.cats.combat = true;
    applyFilterUI();
  }
  persist();
  render();
});

window.addEventListener("keydown", (e) => {
  if (e.key === "/" && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const tag = (e.target && e.target.tagName) || "";
    if (tag === "INPUT" || tag === "TEXTAREA" || e.target?.isContentEditable) return;
    const search = $("#search");
    if (!search) return;
    e.preventDefault();
    search.focus();
    search.select();
  }
});

$("#btnGames").addEventListener("click", () => {
  $("#gamePicker").classList.toggle("hidden");
  if (!$("#gamePicker").classList.contains("hidden")) renderPicker();
});

$("#gamePicker").addEventListener("change", (e) => {
  const input = e.target.closest("[data-game]");
  if (!input) return;
  const id = input.dataset.game;
  if (input.checked) {
    if (!state.enabled.includes(id)) state.enabled.push(id);
  } else {
    state.enabled = state.enabled.filter((x) => x !== id);
    if (state.enabled.length === 0) {
      state.enabled = [id];
      input.checked = true;
    }
  }
  persist();
  renderPicker();
  render();
});

$("#gamePicker").addEventListener("click", (e) => {
  if (e.target.closest("[data-pick-all]")) {
    e.preventDefault();
    state.enabled = allGames().map((g) => g.id);
    persist();
    renderPicker();
    render();
    return;
  }
  if (e.target.closest("[data-pick-none]")) {
    e.preventDefault();
    // 至少保留当前第一个已启用，避免空列表
    const keep = state.enabled[0] || DEFAULT_ENABLED[0];
    state.enabled = [keep];
    persist();
    renderPicker();
    render();
    return;
  }
  const move = e.target.closest("[data-move]");
  if (move) {
    e.preventDefault();
    e.stopPropagation();
    moveEnabled(move.dataset.game, move.dataset.move === "up" ? -1 : 1);
    return;
  }
  const rm = e.target.closest("[data-rm]");
  if (!rm) return;
  e.preventDefault();
  const id = rm.dataset.rm;
  saveCustomGames(loadCustomGames().filter((g) => g.id !== id));
  state.enabled = state.enabled.filter((x) => x !== id);
  persist();
  renderPicker();
  render();
});

$("#gamePicker").addEventListener("submit", (e) => {
  const addGame = e.target.closest("#customAdd");
  const addEv = e.target.closest("#customEventAdd");
  if (addGame) {
    e.preventDefault();
    const fd = new FormData(addGame);
    const name = String(fd.get("name") || "").trim();
    if (!name) return;
    const icon = String(fd.get("icon") || "").trim();
    const id = "custom-" + Date.now().toString(36);
    const list = loadCustomGames();
    list.push({
      id,
      name,
      en: "CUSTOM",
      icon: icon || "./icons/custom.svg",
      events: [],
    });
    saveCustomGames(list);
    if (!state.enabled.includes(id)) state.enabled.push(id);
    persist();
    addGame.reset();
    renderPicker();
    loadAll();
    return;
  }
  if (addEv) {
    e.preventDefault();
    const fd = new FormData(addEv);
    const gameId = String(fd.get("gameId") || "");
    const title = String(fd.get("title") || "").trim();
    const start = String(fd.get("start") || "");
    const end = String(fd.get("end") || "");
    if (!gameId || !title || !start || !end) return;
    const startIso = new Date(start).toISOString();
    const endIso = new Date(end).toISOString();
    if (!(new Date(endIso) > new Date(startIso))) {
      alert("结束时间需晚于开始时间");
      return;
    }
    const list = loadCustomGames();
    const g = list.find((x) => x.id === gameId);
    if (!g) return;
    g.events = g.events || [];
    g.events.push({
      id: `${gameId}-${Date.now()}`,
      title,
      header: title,
      banner: "",
      start: startIso,
      end: endIso,
      hasSchedule: true,
      category: "combat",
      fuzzy: false,
    });
    saveCustomGames(list);
    addEv.reset();
    renderPicker();
    loadAll();
  }
});

$("#btnRefresh").addEventListener("click", () => {
  loadAll().catch((err) => {
    $("#meta").textContent = String(err.message || err);
  });
});

const searchInput = $("#search");
if (searchInput) {
  let searchTimer = 0;
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.query = searchInput.value || "";
      render();
    }, 120);
  });
}

$("#btnFoldAll")?.addEventListener("click", () => {
  for (const g of visibleGames()) state.collapsed[g.id] = true;
  persist();
  render();
});
$("#btnExpandAll")?.addEventListener("click", () => {
  for (const g of visibleGames()) state.collapsed[g.id] = false;
  persist();
  render();
});

const toTop = $("#toTop");
const topSticky = document.querySelector(".top-sticky");
window.addEventListener(
  "scroll",
  () => {
    const y = window.scrollY || 0;
    if (toTop) toTop.classList.toggle("hidden", y < 420);
    if (topSticky) topSticky.classList.toggle("is-scrolled", y > 8);
  },
  { passive: true }
);
toTop?.addEventListener("click", () => {
  window.scrollTo({ top: 0, behavior: "smooth" });
});

applyFilterUI();
renderPicker();
loadAll().catch((err) => {
  $("#meta").textContent = String(err.message || err);
});

import { $ } from "./util.js";
import { allGames, state } from "./state.js";

let activeId = "";
let filterQ = "";

export function setSidebarFilter(q) {
  filterQ = (q || "").trim().toLowerCase();
  renderSidebar();
}

export function setActiveGame(id) {
  activeId = id || "";
  document.querySelectorAll(".sidebar-item").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.game === activeId);
  });
  const sel = $("#mobileGameSelect");
  if (sel && activeId) sel.value = activeId;
}

function countFor(game) {
  const load = state.loadState[game.id] || "idle";
  if (load === "loading") return "…";
  if (load === "error") return "!";
  if (load !== "ready") return "·";
  const events = state.byGame[game.id]?.events || game.events || [];
  return String(events.length);
}

export function renderSidebar() {
  const nav = $("#sidebarNav");
  const sel = $("#mobileGameSelect");
  if (!nav) return;

  const enabled = new Set(state.enabled);
  let games = allGames();
  if (filterQ) {
    games = games.filter((g) => `${g.name} ${g.en} ${g.id}`.toLowerCase().includes(filterQ));
  }

  nav.innerHTML = games
    .map((g) => {
      const on = enabled.has(g.id);
      const load = state.loadState[g.id] || "idle";
      const err = load === "error";
      const accentVar = g.accent ? `var(--${g.accent}, var(--accent))` : "var(--accent)";
      return `<button type="button" class="sidebar-item ${on ? "" : "is-off"} ${err ? "is-error" : ""} ${
        g.id === activeId ? "is-active" : ""
      }" data-game="${g.id}" style="--g-accent:${accentVar}" title="${g.en}">
        <img src="${g.icon}" alt="" onerror="this.src='./icons/custom.svg'" />
        <span class="si-name">${g.name}</span>
        <span class="si-count">${on ? countFor(g) : "关"}</span>
      </button>`;
    })
    .join("");

  if (sel) {
    const list = allGames().filter((g) => enabled.has(g.id));
    sel.innerHTML =
      list.map((g) => `<option value="${g.id}">${g.name}</option>`).join("") ||
      `<option value="">无游戏</option>`;
    if (activeId) sel.value = activeId;
  }
}

export function openMobileSidebar() {
  document.body.classList.add("sidebar-open");
  $("#btnSidebar")?.setAttribute("aria-expanded", "true");
  $("#sidebarScrim")?.classList.remove("hidden");
  $("#sidebarScrim")?.setAttribute("aria-hidden", "false");
}

export function closeMobileSidebar() {
  document.body.classList.remove("sidebar-open");
  $("#btnSidebar")?.setAttribute("aria-expanded", "false");
  $("#sidebarScrim")?.classList.add("hidden");
  $("#sidebarScrim")?.setAttribute("aria-hidden", "true");
}

export function toggleMobileSidebar() {
  if (document.body.classList.contains("sidebar-open")) closeMobileSidebar();
  else openMobileSidebar();
}

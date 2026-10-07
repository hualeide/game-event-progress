/**
 * 真实 Chromium。render/format/util/detail 用源码，state/data 为虚构模块。
 * 运行：node --test test_render_dom.cjs
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { after, before, test } = require("node:test");
const { chromium } = require("playwright");

const JS = path.join(__dirname, "public", "js");
const V = "20260903v15";
const PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64",
);

const HTML = `<!DOCTYPE html><html><body>
<main id="games"></main>
<div id="gamePicker"></div>
<span id="meta"></span>
<p id="empty" class="hidden"></p>
<input id="hideEmpty" type="checkbox" />
<div id="filters">
  <input data-cat="combat" type="checkbox" />
  <input data-cat="gacha" type="checkbox" />
  <input data-cat="web" type="checkbox" />
  <input data-cat="event" type="checkbox" />
</div>
<div id="detail" class="detail hidden" aria-hidden="true">
  <p id="detailGame"></p>
  <h2 id="detailTitle"></h2>
  <div id="detailTags"></div>
  <div id="detailBanner"></div>
  <div id="detailBody"></div>
  <footer id="detailFoot"></footer>
</div>
<script type="module" src="/js/harness.js"></script>
</body></html>`;

const STATE = `
export const eventIndex = new Map();
export const state = {
  byGame: {},
  cats: { combat: true, gacha: true, web: true, event: true },
  loadState: {},
  enabled: [],
  collapsed: {},
  hideEmpty: false,
  query: "",
  status: {},
};
let fixtures = [];
export function allGames() { return fixtures; }
export function loadCustomGames() { return fixtures.filter((g) => g.custom); }
export function setFixtures(list) { fixtures = list; }
export function persist() {}
export function toolsFor(game) { return game.tools || []; }
export function wikiFor(game) { return game.wiki?.url ? game.wiki : null; }
export const CAT_ORDER = ["combat", "gacha", "web", "event"];
export const gamesMeta = { byId: {} };
export const DATA_BASES = [];
export function remoteConfigUrl() { return ""; }
export function importConfig() {}
export function metaFor() { return {}; }
`;

const DATA = `
import { state } from "./state.js?v=${V}";
export async function loadGame(game) {
  state.loadState[game.id] = "ready";
  return state.byGame[game.id];
}
export async function ensureGameLoaded(id) {
  state.loadState[id] = "ready";
  return state.byGame[id];
}
`;

const HARNESS = `
import { cardHtml, gameRowHtml, patchGameRow, render, renderPicker, toolsHtml } from "./render.js?v=${V}";
import { closeDetail, openDetail } from "./detail.js?v=${V}";
import { eventIndex, setFixtures, state } from "./state.js?v=${V}";
window.__ui = { cardHtml, gameRowHtml, patchGameRow, render, renderPicker, toolsHtml, closeDetail, openDetail, eventIndex, setFixtures, state };
`;

const FILES = {
  "/js/render.js": path.join(JS, "render.js"),
  "/js/detail.js": path.join(JS, "detail.js"),
  "/js/format.js": path.join(JS, "format.js"),
  "/js/util.js": path.join(JS, "util.js"),
};

let browser;
let context;
let page;
const errors = [];

before(async () => {
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext({ serviceWorkers: "block" });
  page = await context.newPage();
  await page.clock.setFixedTime(new Date("2026-10-07T08:30:00+08:00"));
  page.on("pageerror", (err) => errors.push(String(err)));
  await page.route("**/*", async (route) => {
    const u = new URL(route.request().url());
    const req = route.request();
    if (u.pathname === "/" || u.pathname === "/index.html") {
      await route.fulfill({ status: 200, contentType: "text/html", body: HTML });
      return;
    }
    if (u.pathname === "/js/state.js") {
      await route.fulfill({ status: 200, contentType: "text/javascript", body: STATE });
      return;
    }
    if (u.pathname === "/js/data.js") {
      await route.fulfill({ status: 200, contentType: "text/javascript", body: DATA });
      return;
    }
    if (u.pathname === "/js/harness.js") {
      await route.fulfill({ status: 200, contentType: "text/javascript", body: HARNESS });
      return;
    }
    const file = FILES[u.pathname];
    if (file) {
      await route.fulfill({ status: 200, contentType: "text/javascript", body: fs.readFileSync(file) });
      return;
    }
    if (req.resourceType() === "image" || u.pathname.endsWith(".svg") || u.pathname.endsWith(".png")) {
      await route.fulfill({ status: 200, contentType: "image/png", body: PNG });
      return;
    }
    await route.abort();
  });
  await page.goto("http://127.0.0.1:9/", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.__ui);
});

after(async () => {
  await context?.close();
  await browser?.close();
});

async function reset() {
  errors.length = 0;
  await page.evaluate(() => {
    const { state, eventIndex, setFixtures } = window.__ui;
    eventIndex.clear();
    state.byGame = {};
    state.loadState = {};
    state.enabled = [];
    state.collapsed = {};
    state.hideEmpty = false;
    state.query = "";
    state.cats = { combat: true, gacha: true, web: true, event: true };
    setFixtures([]);
    document.querySelector("#games").innerHTML = "";
    document.querySelector("#gamePicker").innerHTML = "";
  });
}

test("外部文本和带引号 id 不拆节点", async () => {
  await reset();
  const gameId = 'ab" data-game-marker="yes';
  const eventId = 'ev" data-event-marker="yes';
  const title = "<b data-title>x</b>";
  const summary = "<i data-sub>x</i>";
  const gameName = "Fake <em data-game>x</em>";
  const toolName = "<b data-tool>x</b>";
  const banner = "https://example.test/a.png?q=1&x=2";
  const icon = "https://example.test/icon.png?q=1&x=2";
  const link = "https://example.test/go?a=1&b=2";
  const toolUrl = "https://example.test/tool?a=1&b=2";
  const en = 'EN&"x';
  await page.evaluate(
    (p) => {
      const { gameRowHtml, setFixtures, state } = window.__ui;
      const game = {
        id: p.gameId,
        name: p.gameName,
        en: p.en,
        icon: p.icon,
        accent: 'warm" data-accent-marker="yes',
        tools: [{ url: p.toolUrl, name: p.toolName, desc: '说明&"' }],
        wiki: { url: "https://example.test/wiki?a=1&b=2", name: "资料" },
      };
      const ev = {
        id: p.eventId,
        title: p.title,
        summary: p.summary,
        banner: p.banner,
        link: p.link,
        hasSchedule: true,
        category: "combat",
        start: "2026-10-07T00:00:00+08:00",
        end: "2027-01-01T00:00:00+08:00",
      };
      setFixtures([game]);
      state.enabled = [game.id];
      state.loadState[game.id] = "ready";
      state.byGame[game.id] = { events: [ev] };
      document.querySelector("#games").innerHTML = gameRowHtml(game, state.byGame[game.id]);
    },
    { gameId, eventId, title, summary, gameName, toolName, banner, icon, link, toolUrl, en },
  );
  assert.equal(await page.locator("b[data-title]").count(), 0);
  assert.equal(await page.locator("i[data-sub]").count(), 0);
  assert.equal(await page.locator("em[data-game]").count(), 0);
  assert.equal(await page.locator("b[data-tool]").count(), 0);
  assert.equal(await page.locator("[data-game-marker]").count(), 0);
  assert.equal(await page.locator("[data-event-marker]").count(), 0);
  assert.equal(await page.locator("[data-accent-marker]").count(), 0);
  assert.equal(await page.locator(".bar-title").innerText(), title);
  assert.equal(await page.locator(".bar-sub").innerText(), summary);
  assert.equal(await page.locator(".game-name").evaluate((el) => el.childNodes[0].textContent), gameName);
  assert.equal(await page.locator(".game-name small").innerText(), en);
  assert.equal(await page.locator("a.tool-link:not(.wiki)").innerText(), toolName);
  assert.equal(await page.locator(".game-row").getAttribute("data-game"), gameId);
  assert.equal(await page.locator(".card").getAttribute("data-event-id"), eventId);
  assert.equal(await page.locator(".card").getAttribute("data-game-id"), gameId);
  assert.equal(await page.locator(".cover-img").getAttribute("src"), banner);
  assert.equal(await page.locator(".cover-link").getAttribute("href"), link);
  assert.equal(await page.locator(".game-icon").getAttribute("src"), icon);
  assert.equal(await page.locator("a.tool-link:not(.wiki)").getAttribute("href"), toolUrl);
  assert.equal(await page.locator("a.tool-link.wiki").getAttribute("href"), "https://example.test/wiki?a=1&b=2");
  assert.equal(await page.locator(".game-icon").getAttribute("onerror"), "this.src='./icons/custom.svg'");
  assert.equal(await page.locator(".cover-img").getAttribute("onload"), "adaptCover(this)");
  assert.equal(
    await page.evaluate((id) => window.__ui.eventIndex.has(id), eventId),
    true,
  );
  assert.deepEqual(errors, []);
});

test("工具条 compact 两条、完整五条", async () => {
  await reset();
  const names = await page.evaluate(() => {
    const { toolsHtml } = window.__ui;
    const tools = [1, 2, 3, 4, 5, 6].map((n) => ({
      url: `https://example.test/t${n}?a=1&b=2`,
      name: `工具${n}`,
      desc: `说明${n}`,
    }));
    const game = { id: "g", name: "甲", tools, wiki: { url: "https://example.test/w?a=1&b=2", name: "资料" } };
    const host = document.createElement("div");
    host.innerHTML = toolsHtml(game, { compact: true }) + toolsHtml(game);
    document.body.appendChild(host);
    const rows = [...host.querySelectorAll("[data-tools]")];
    return rows.map((row) => row.querySelectorAll("a.tool-link:not(.wiki)").length);
  });
  assert.deepEqual(names, [2, 5]);
});

test("picker 的 option 和名字不拆节点", async () => {
  await reset();
  const id = 'id" data-opt="yes';
  const name = "<b data-pick>x</b>";
  await page.evaluate(
    ({ id, name }) => {
      const { renderPicker, setFixtures, state } = window.__ui;
      const game = { id, name, en: "X", icon: "./icons/custom.svg", custom: true, tools: [], wiki: null };
      setFixtures([game]);
      state.enabled = [id];
      renderPicker();
    },
    { id, name },
  );
  assert.equal(await page.locator("b[data-pick]").count(), 0);
  assert.equal(await page.locator("[data-opt]").count(), 0);
  assert.equal(await page.locator("option:not([value=''])").getAttribute("value"), id);
  assert.equal(await page.locator("option:not([value=''])").innerText(), name);
  assert.equal(await page.locator(".pick-name").innerText(), name);
  assert.equal(await page.locator(".pick-item input").getAttribute("data-game"), id);
});

test("进度、预告、已结束和筛选顺序", async () => {
  await reset();
  await page.evaluate(() => {
    const { render, setFixtures, state } = window.__ui;
    const events = [
      { id: "ended", title: "已结束卡", hasSchedule: true, category: "combat", start: "2026-01-01T00:00:00+08:00", end: "2026-01-10T00:00:00+08:00" },
      { id: "zero", title: "零进度卡", hasSchedule: true, category: "combat", start: "2026-10-07T08:00:00+08:00", end: "2027-10-07T00:00:00+08:00" },
      { id: "soon", title: "即将结束卡", hasSchedule: true, category: "combat", start: "2026-10-01T00:00:00+08:00", end: "2026-10-07T23:00:00+08:00" },
      { id: "preview", title: "未来卡", hasSchedule: true, category: "combat", start: "2026-12-01T00:00:00+08:00", end: "2026-12-10T00:00:00+08:00" },
      { id: "gacha", title: "寻访卡", hasSchedule: true, category: "gacha", start: "2026-10-01T00:00:00+08:00", end: "2026-12-01T00:00:00+08:00" },
    ];
    const a = { id: "ga", name: "甲游戏", en: "A", icon: "./icons/custom.svg", accent: "ark", tools: [], wiki: null };
    const b = { id: "gb", name: "乙游戏", en: "B", icon: "./icons/custom.svg", accent: "ba", tools: [], wiki: null };
    setFixtures([a, b]);
    state.enabled = ["gb", "ga"];
    state.collapsed = { gb: true };
    state.loadState = { ga: "ready", gb: "ready" };
    state.byGame = { ga: { events }, gb: { events: [] } };
    render();
  });
  const order = await page.locator(".game-row").evaluateAll((rows) => rows.map((r) => r.getAttribute("data-game")));
  assert.deepEqual(order, ["gb", "ga"]);
  assert.match(await page.locator('.game-row[data-game="gb"]').getAttribute("class"), /collapsed/);
  const titles = await page.locator('.game-row[data-game="ga"] .bar-title').allInnerTexts();
  assert.deepEqual(titles, ["即将结束卡", "寻访卡", "零进度卡", "未来卡"]);
  assert.equal(await page.locator(".card.done").count(), 0);
  const zero = page.locator('.card[data-event-id="zero"]');
  assert.match(await zero.locator(".badge").first().innerText(), /进行中/);
  assert.equal(await zero.locator(".pct-num").innerText(), "0%");
  assert.match(await page.locator('.card[data-event-id="preview"] .badge').first().innerText(), /预告/);
  const ended = await page.evaluate(() => {
    const game = window.__ui.state.byGame.ga && { id: "ga", accent: "ark" };
    const html = window.__ui.cardHtml(game, window.__ui.state.byGame.ga.events[0]);
    const box = document.createElement("div");
    box.id = "ended-box";
    box.innerHTML = html;
    document.body.appendChild(box);
    return {
      badge: box.querySelector(".badge").textContent,
      pct: box.querySelector(".pct-num").textContent,
    };
  });
  assert.equal(ended.badge, "已结束");
  assert.equal(ended.pct, "100%");
  await page.evaluate(() => {
    window.__ui.state.cats.gacha = false;
    window.__ui.render();
  });
  assert.equal(await page.locator('.card[data-event-id="gacha"]').count(), 0);
  assert.equal(await page.locator('.card[data-event-id="zero"]').count(), 1);
});

test("带引号的 gameId 可以 patch 并打开详情", async () => {
  await reset();
  const gameId = 'ab" data-game-marker="yes';
  const eventId = 'ev" data-event-marker="yes';
  await page.evaluate(
    ({ gameId, eventId }) => {
      const { gameRowHtml, setFixtures, state } = window.__ui;
      const game = { id: gameId, name: "甲", en: "A", icon: "./icons/custom.svg", accent: "ark", tools: [], wiki: null };
      const ev = {
        id: eventId,
        title: "可打开",
        hasSchedule: true,
        category: "combat",
        banner: "https://example.test/ok.png?a=1&b=2",
        link: "https://example.test/go?a=1&b=2",
        start: "2026-10-01T00:00:00+08:00",
        end: "2026-10-20T00:00:00+08:00",
      };
      setFixtures([game]);
      state.enabled = [gameId];
      state.loadState[gameId] = "ready";
      state.byGame[gameId] = { events: [ev] };
      document.querySelector("#games").innerHTML = gameRowHtml(game, state.byGame[gameId]);
      return window.__ui.patchGameRow(gameId).then(() => {
        window.__ui.openDetail(gameId, eventId);
      });
    },
    { gameId, eventId },
  );
  assert.equal(await page.locator(".game-row").count(), 1);
  assert.equal(await page.locator("#detail.hidden").count(), 0);
  assert.equal(
    await page.evaluate(() => location.hash),
    `#/event/${encodeURIComponent(gameId)}/${encodeURIComponent(eventId)}`,
  );
  await page.evaluate(() => window.__ui.closeDetail());
  assert.equal(await page.locator("#detail.hidden").count(), 1);
  assert.equal(await page.evaluate(() => location.hash), "");
  assert.deepEqual(errors, []);
});

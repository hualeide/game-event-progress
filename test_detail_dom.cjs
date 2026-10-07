/**
 * 真实 Chromium。只加载 detail/format/util，state/data 为虚构模块。
 * 运行：node test_detail_dom.cjs（playwright 走 NODE_PATH，不安装）。
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { after, before, test } = require("node:test");
const { chromium } = require("playwright");

const JS = path.join(__dirname, "public", "js");
const V = "20260903v15";

const HTML = `<!DOCTYPE html><html><body>
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
export const state = { byGame: {}, cats: {}, loadState: {} };
export const CAT_ORDER = ["combat", "gacha", "web", "event"];
export const gamesMeta = { byId: {} };
export const DATA_BASES = [];
export function remoteConfigUrl() { return ""; }
export function importConfig() {}
export function metaFor() { return {}; }
export function toolsFor(game) { return game.tools || []; }
export function wikiFor(game) { return game.wiki?.url ? game.wiki : null; }
export function allGames() { return []; }
`;

const DATA = `export async function ensureGameLoaded() { return null; }`;

const HARNESS = `
import { openDetail, closeDetail } from "./detail.js?v=${V}";
import { eventIndex } from "./state.js?v=${V}";
window.__detail = { openDetail, closeDetail, eventIndex };
`;

const FILES = {
  "/js/detail.js": path.join(JS, "detail.js"),
  "/js/format.js": path.join(JS, "format.js"),
  "/js/util.js": path.join(JS, "util.js"),
};

function noInjected(root) {
  const bad = [];
  for (const el of root.querySelectorAll("*")) {
    for (const a of el.attributes) {
      if (a.name.toLowerCase().startsWith("on")) bad.push(a.name);
      if (["data-banner", "data-title", "data-range", "data-cat", "data-wiki", "data-tool", "data-days", "data-x"].includes(a.name)) {
        bad.push(a.name);
      }
    }
    if (el.tagName === "SCRIPT") bad.push("script");
  }
  return bad;
}

let browser;
let context;
let page;
const errors = [];

before(async () => {
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext({ serviceWorkers: "block" });
  page = await context.newPage();
  page.on("pageerror", (err) => errors.push(String(err)));
    await page.route("**/*", async (route) => {
      const u = new URL(route.request().url());
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
        await route.fulfill({
          status: 200,
          contentType: "text/javascript",
          body: fs.readFileSync(file),
        });
        return;
      }
      await route.abort();
    });
  await page.goto("http://127.0.0.1:9/", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => window.__detail);
});

after(async () => {
  await context?.close();
  await browser?.close();
});

test("恶意字段留在属性里", async () => {
    const banner = 'https://example.test/a.png" data-banner="yes';
    const title = 'Fake" data-title="yes';
    const label = '<b data-range="yes">FakeRange</b>';
    const category = 'evt" data-cat="yes';
    const days = {
      totalDays: '9<img data-days="yes">',
      elapsedDays: '1" data-x="y',
      remainDays: "2&3<4>",
    };
    const jump = 'https://example.test/go?a=1&b=2" data-x="yes';
    const wikiUrl = 'https://example.test/wiki?a=1&b=2" data-wiki="yes';
    const toolUrl = 'https://example.test/tool?a=1&b=2" data-tool="yes';
    const wikiName = 'W<iki>&"';
    const toolName = 'T<ool>&"';
    const toolDesc = 'D<esc>&"';

    await page.evaluate(
      ({ banner, title, label, category, days, jump, wikiUrl, toolUrl, wikiName, toolName, toolDesc }) => {
        const { openDetail, eventIndex } = window.__detail;
        eventIndex.clear();
        eventIndex.set("e-bad", {
          game: {
            id: "fake",
            name: "虚构",
            en: "FAKE",
            wiki: { url: wikiUrl, name: wikiName },
            tools: [{ url: toolUrl, name: toolName, desc: toolDesc }],
          },
          ev: {
            id: "e-bad",
            title,
            banner,
            link: jump,
            start: "2026-08-01T12:00:00+08:00",
            end: "2026-08-03T12:00:00+08:00",
            days,
            allRanges: [
              {
                label,
                category,
                start: "2026-08-01T12:00:00+08:00",
                end: "2026-08-02T12:00:00+08:00",
              },
            ],
          },
        });
        openDetail("fake", "e-bad");
      },
      { banner, title, label, category, days, jump, wikiUrl, toolUrl, wikiName, toolName, toolDesc },
    );

    const injected = await page.locator("#detail").evaluate(noInjected);
    assert.deepEqual(injected, []);
    const img = page.locator("#detailBanner img");
    assert.equal(await img.getAttribute("src"), banner);
    assert.equal(await img.getAttribute("alt"), title);
    assert.equal(await img.evaluate((el) => el.hasAttribute("data-banner")), false);
    assert.equal(await img.evaluate((el) => el.hasAttribute("data-title")), false);
    assert.equal(await page.locator("b[data-range]").count(), 0);
    assert.equal(await page.locator(".range-list b").innerText(), label);
    const when = await page.locator(".range-when").innerText();
    assert.equal(await page.locator(".tl-bar").getAttribute("title"), `${label} ${when}`);
    const tlClass = await page.locator(".tl-bar").getAttribute("class");
    assert.equal(tlClass.includes('cat-evt" data-cat="yes'), true);
    assert.match(await page.locator(".detail-days").innerText(), /1" data-x="y/);
    assert.match(await page.locator(".detail-days").innerText(), /9<img data-days="yes">/);
    assert.match(await page.locator(".detail-days").innerText(), /2&3<4>/);
    assert.equal(await page.locator("#detailFoot a.primary").getAttribute("href"), jump);
    assert.equal(await page.locator('#detailFoot a.ghost[href*="wiki"]').getAttribute("href"), wikiUrl);
    const footTool = page.locator("#detailFoot a.ghost[title]");
    assert.equal(await footTool.getAttribute("href"), toolUrl);
    assert.equal(await footTool.getAttribute("title"), toolDesc);
    assert.equal(await footTool.innerText(), toolName);
    const relWiki = page.locator("a.tool-link.wiki");
    assert.equal(await relWiki.getAttribute("href"), wikiUrl);
    assert.equal(await relWiki.locator("small").innerText(), "资料站");
    assert.equal(await relWiki.evaluate((el) => el.childNodes[0].textContent), wikiName);
    const relTool = page.locator("a.tool-link:not(.wiki)");
    assert.equal(await relTool.getAttribute("href"), toolUrl);
    assert.equal(await relTool.getAttribute("title"), toolDesc);
    assert.equal(await relTool.evaluate((el) => el.childNodes[0].textContent), toolName);
    assert.equal(await relTool.locator("small").innerText(), toolDesc);
    assert.deepEqual(errors, []);
});

test("正常详情、高亮与关闭", async () => {
    const safeJump = "https://example.test/go?a=1&b=中文";
    const safeWiki = "https://example.test/wiki?a=1&b=2";
    const safeTool = "https://example.test/tool?q=甲&x=1";
    const safeBanner = "https://example.test/封面.png?q=1&x=2";
    await page.evaluate(
      ({ safeJump, safeWiki, safeTool, safeBanner }) => {
        const { openDetail, eventIndex } = window.__detail;
        const ranges = Array.from({ length: 12 }, (_, i) => ({
          label: `时段${i + 1}`,
          category: "event",
          start: `2026-08-${String(i + 1).padStart(2, "0")}T12:00:00+08:00`,
          end: `2026-08-${String(i + 1).padStart(2, "0")}T18:00:00+08:00`,
        }));
        eventIndex.clear();
        eventIndex.set("e-ok", {
          game: {
            id: "fake",
            name: "虚构",
            en: "FAKE",
            wiki: { url: safeWiki, name: "资料" },
            tools: [{ url: safeTool, name: "工具", desc: "说明" }],
          },
          ev: {
            id: "e-ok",
            title: "正常活动",
            banner: safeBanner,
            link: safeJump,
            start: "2026-08-01T12:00:00+08:00",
            end: "2026-08-20T12:00:00+08:00",
            days: { elapsedDays: 1.5, totalDays: 19, remainDays: 17.5 },
            allRanges: ranges,
            body: "活动时间：8月1日12:00\n【道具】",
          },
        });
        eventIndex.set("e-unknown", {
          game: { id: "fake", name: "虚构", en: "FAKE", tools: [], wiki: null },
          ev: { id: "e-unknown", title: "未知时段", banner: "" },
        });
        openDetail("fake", "e-ok");
      },
      { safeJump, safeWiki, safeTool, safeBanner },
    );
    assert.equal(await page.locator("#detailBanner img").getAttribute("src"), safeBanner);
    assert.equal(await page.locator("#detailFoot a.primary").getAttribute("href"), safeJump);
    assert.equal(await page.locator("a.tool-link.wiki").getAttribute("href"), safeWiki);
    assert.equal(await page.locator("a.tool-link:not(.wiki)").getAttribute("href"), safeTool);
    assert.equal(await page.locator(".tl-bar").count(), 10);
    assert.equal(await page.locator(".range-list li").count(), 12);
    assert.equal(await page.locator(".range-list .cat-event").count(), 12);
    assert.equal(await page.locator(".hl-time").count(), 1);
    assert.equal(await page.locator(".hl-item").innerText(), "【道具】");
    assert.match(await page.locator(".detail-days").innerText(), /已过 1\.5 \/ 共 19 天/);
    assert.equal(await page.locator("[data-copy-link]").count(), 1);
    assert.equal(await page.locator("#detailFoot [data-close-detail]").count(), 1);
    assert.equal(await page.evaluate(() => location.hash), "#/event/fake/e-ok");
    await page.evaluate(() => window.__detail.openDetail("fake", "e-unknown"));
    assert.match(await page.locator(".detail-meta").innerText(), /\?/);
    assert.equal(await page.locator("#detailBanner img").count(), 0);
    await page.evaluate(() => window.__detail.closeDetail());
    assert.equal(await page.locator("#detail.hidden").count(), 1);
    assert.equal(await page.locator("#detail").getAttribute("aria-hidden"), "true");
    assert.equal(await page.evaluate(() => location.hash), "");
    assert.deepEqual(errors, []);
});

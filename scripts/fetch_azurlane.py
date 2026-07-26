#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从碧蓝航线 Bwiki「港区改建」公告解析限时活动 / 建造。"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DATA,
    TZ,
    build_event,
    cache_cover,
    http_get_json,
    make_dt,
    now_cn,
    write_events,
)

API = "https://wiki.biligame.com/blhx/api.php"
UA = {"User-Agent": "Mozilla/5.0 GameEventCal/1.1", "Accept": "application/json"}
LINK_BASE = "https://wiki.biligame.com/blhx/"
CACHE = DATA / "cache" / "azurlane"

TITLE_RE = re.compile(r"^(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日(?P<h>\d{1,2}):(?P<mi>\d{2})港区改建$")

# 开启限时大型活动'''复刻：绽放于辉光之城'''，活动时间6月18日维护后~6月25日维护前
# 开启限时活动「远航回礼」（7月9日维护后~7月22日23:59）
EVENT_RE = re.compile(
    r"(?P<label>开启限时大型活动|开启限时联动复刻活动|开启限时联动活动|开启限时复刻活动|"
    r"开启限时特殊活动|开启限时活动|开启新一期|开启下一期|开启活动|复刻[：:])\s*"
    r"[「『\"]?(?P<name>[^」』\"\n]{2,48}?)[」』\"]?"
    r"(?:活动)?"
    r"(?:"
    r"[，,]\s*活动时间(?P<span1>[^。\n；;]{6,80})"
    r"|"
    r"[（(](?P<span2>[^）)\n]{6,80})[）)]"
    r")",
)

# 限时建造期间 / 开启限时建造
BUILD_RE = re.compile(
    r"(?P<label>限时建造|限时重返建造)"
    r"[^。\n]{0,60}?"
    r"(?:"
    r"活动时间(?P<span1>[^。\n]{6,60})"
    r"|"
    r"[（(](?P<span2>[^）)\n]{6,60})[）)]"
    r")",
)

# 「科研」之类不算
SKIP = re.compile(r"礼包|换装商店|优惠|研发礼包|兑换商店|家具|抵扣|体验礼包|网页支付")

# 「信标·META」限时开放「布里斯托尔·META」挑战，开放时间6月5日维护后~9月4日维护
META_RE = re.compile(
    r"「信标·META」限时开放「(?:\{\{小图标\|)?(?P<name>[^」{}|\n]{2,40}?)(?:\}\})?」"
    r"挑战[，,]\s*开放时间(?P<span>[^。\n；;]{6,80})"
)

PORTAL_RE = re.compile(r"专题传送门\|([^}|]+)")

# 活动名关键词 → 优先配图文件名片段
COVER_FILE_HINTS: list[tuple[str, tuple[str, ...]]] = [
    ("特别竞拍", ("拍卖会请柬", "竞拍", "拍卖")),
    ("自动步兵", ("A2换装", "2B换装", "白之契约", "四o式战术刀")),
    ("人形之旅", ("A2换装", "2B换装")),
    ("怪谈纪实", ("怪谈", "白夜")),
    ("世界巡游", ("世界巡游",)),
    ("限界挑战", ("限界对手", "限界挑战")),
    ("信标", ("官方海报", "META立绘", "Camplogo_META")),
]


def wiki_json(params: dict, retries: int = 4) -> dict:
    q = urllib.parse.urlencode({**params, "format": "json"})
    url = f"{API}?{q}"
    last: Exception | None = None
    for i in range(retries):
        try:
            return http_get_json(url, UA)
        except HTTPError as e:
            last = e
            # 567 / 429 等限流
            time.sleep(1.2 * (i + 1))
        except Exception as e:
            last = e
            time.sleep(0.8 * (i + 1))
    raise last or RuntimeError("wiki_json failed")


def list_rebuild_pages(year: int = 2026) -> list[str]:
    def key(t: str):
        m = TITLE_RE.match(t)
        return tuple(int(m[k]) for k in ("y", "m", "d", "h", "mi"))

    titles: list[str] = []
    try:
        pages = wiki_json(
            {"action": "query", "list": "allpages", "apprefix": f"{year}年", "aplimit": "max"}
        ).get("query", {}).get("allpages", [])
        titles = [p["title"] for p in pages if "港区改建" in p["title"] and TITLE_RE.match(p["title"])]
    except Exception as e:
        print(f"  [warn] 列表失败，改用本地缓存: {e}")

    if CACHE.exists():
        for p in CACHE.glob("*.txt"):
            # 文件名还原不完全，读首行或用已知模式扫描目录旁 metadata
            pass

    # 已知近期维护（wiki 限流时兜底）
    fallback = [
        f"{year}年5月28日10:00港区改建",
        f"{year}年6月5日10:00港区改建",
        f"{year}年6月12日10:00港区改建",
        f"{year}年6月18日10:00港区改建",
        f"{year}年6月25日10:00港区改建",
        f"{year}年7月9日10:00港区改建",
        f"{year}年7月16日10:00港区改建",
        f"{year}年7月23日10:00港区改建",
        f"{year}年7月30日10:00港区改建",
        f"{year}年8月6日10:00港区改建",
        f"{year}年8月13日10:00港区改建",
    ]
    for t in fallback:
        if TITLE_RE.match(t) and t not in titles:
            titles.append(t)

    titles = [t for t in titles if TITLE_RE.match(t)]
    titles.sort(key=key)
    return titles


def cache_path(title: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", title)
    return CACHE / f"{safe}.txt"


def page_wikitext(title: str, *, refresh: bool = False) -> str:
    from common import http_get

    cached = cache_path(title)
    if cached.exists() and cached.stat().st_size > 100 and not refresh:
        return cached.read_text(encoding="utf-8")

    url = "https://wiki.biligame.com/blhx/index.php?" + urllib.parse.urlencode(
        {"title": title, "action": "raw"}
    )
    try:
        text = http_get(url, UA, timeout=12).decode("utf-8", "replace")
        if len(text) > 200:
            cached.write_text(text, encoding="utf-8")
            return text
    except HTTPError as e:
        if e.code == 404:
            return ""
        if cached.exists() and cached.stat().st_size > 100:
            print(f"  [cache] {title}")
            return cached.read_text(encoding="utf-8")
        raise
    except Exception as e:
        if cached.exists() and cached.stat().st_size > 100:
            print(f"  [cache] {title}")
            return cached.read_text(encoding="utf-8")
        raise e
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    return ""


_FILE_URL: dict[str, str] = {}


def file_url(filename: str, *, min_bytes: int = 8000) -> str:
    """Wiki 文件名 → 直链（带缓存）。过小的图标图跳过。"""
    filename = (filename or "").strip().replace(" ", "_")
    if not filename:
        return ""
    key = f"{filename}|{min_bytes}"
    if key in _FILE_URL:
        return _FILE_URL[key]
    try:
        info = wiki_json(
            {
                "action": "query",
                "titles": f"File:{filename}",
                "prop": "imageinfo",
                "iiprop": "url|size|thumburl",
                "iiurlwidth": 960,
            }
        )
        pages = info.get("query", {}).get("pages") or {}
        for p in pages.values():
            if p.get("missing") is not None or int(p.get("ns", 0)) < 0:
                continue
            ii = (p.get("imageinfo") or [{}])[0]
            size = int(ii.get("size") or 0)
            url = ii.get("thumburl") or ii.get("url") or ""
            # 原图过小通常是图标；略放宽阈值（cache_cover 也有 8KB 门槛）
            if url and size >= min_bytes:
                _FILE_URL[key] = url
                return url
            if url and size >= 3000 and ii.get("thumburl"):
                # 有缩略放大链时仍可用
                _FILE_URL[key] = ii["thumburl"]
                return ii["thumburl"]
    except Exception:
        pass
    _FILE_URL[key] = ""
    return ""


def page_banner(title: str, *, hint: str = "") -> str:
    try:
        data = wiki_json({"action": "parse", "page": title, "prop": "images"})
    except Exception:
        return ""
    images = data.get("parse", {}).get("images") or []
    # 跳过常见无用小图 / 系列图标
    skip = re.compile(r"icon|Icon|头像|贴纸|emoji|按钮|logo|小图标|图标", re.I)
    prefer_kw = re.compile(r"banner|Banner|活动|专题|KV|对手", re.I)
    hint_bits = [h for h in re.split(r"[：:·・\s]+", hint or "") if len(h) >= 2]

    def score(name: str) -> int:
        s = 0
        if any(h in name for h in hint_bits):
            s += 50
        if prefer_kw.search(name):
            s += 20
        if skip.search(name):
            s -= 80
        return s

    ranked = sorted(images, key=score, reverse=True)
    for name in ranked:
        if not name or skip.search(name):
            continue
        url = file_url(name, min_bytes=8000)
        if url:
            return url
    return ""


def nearby_file(wt: str, name: str) -> str:
    """活动名附近的 [[File:/文件:]]。"""
    if not name or not wt:
        return ""
    idx = wt.find(name)
    if idx < 0 and len(name) > 4:
        idx = wt.find(name[:4])
    if idx < 0:
        return ""
    window = wt[max(0, idx - 240) : idx + 480]
    m = re.search(r"\[\[(?:File|文件):([^|\]]+)", window, re.I)
    return (m.group(1) or "").strip() if m else ""


def portal_pages(wt: str) -> list[str]:
    return [m.group(1).strip() for m in PORTAL_RE.finditer(wt or "")]


def resolve_hint_file(hint: str) -> str:
    """提示词 → 文件直链。"""
    for cand in (
        f"{hint}.jpg",
        f"{hint}.png",
        f"{hint}T0.jpg",
        f"{hint}T0.png",
        f"{hint}官方海报.jpg",
    ):
        url = file_url(cand, min_bytes=3000)
        if url:
            return url
    try:
        data = wiki_json(
            {"action": "query", "list": "allimages", "aiprefix": hint, "ailimit": 8}
        )
        for it in data.get("query", {}).get("allimages") or []:
            url = file_url(it.get("name") or "", min_bytes=8000)
            if url:
                return url
    except Exception:
        pass
    return ""


def page_images(title: str) -> list[str]:
    try:
        data = wiki_json({"action": "parse", "page": title, "prop": "images"})
    except Exception:
        return []
    return list(data.get("parse", {}).get("images") or [])


def pick_from_filenames(
    filenames: list[str],
    name: str,
    *,
    forbid: set[str] | None = None,
) -> str:
    """按活动名在文件名列表里打分选图。"""
    forbid = forbid or set()
    skip = re.compile(r"icon|Icon|头像|贴纸|教材|物资|科技箱|喵箱|logo|小图标|图标", re.I)
    hint_bits = [h for h in re.split(r"[：:·・\s！!]+", name or "") if len(h) >= 2]
    file_hints: list[str] = []
    for key, hints in COVER_FILE_HINTS:
        if key in name:
            file_hints.extend(hints)

    scored: list[tuple[int, str, str]] = []
    for fn in filenames:
        if not fn or skip.search(fn):
            continue
        url = file_url(fn, min_bytes=8000)
        if not url or url in forbid:
            continue
        score = 0
        if any(h in fn for h in hint_bits):
            score += 60
        if any(h in fn for h in file_hints):
            score += 80
        if re.search(r"换装|海报|立绘|对手|请柬|专题|banner|Banner", fn, re.I):
            score += 25
        if score:
            scored.append((score, fn, url))
    if not scored:
        return ""
    scored.sort(key=lambda x: -x[0])
    return scored[0][2]


def pick_event_banner(
    name: str,
    page_title: str,
    wt: str,
    page_ban: str,
    *,
    forbid: set[str] | None = None,
    portals: list[str] | None = None,
) -> str:
    """单活动配图：提示文件 → 专题页 → 同名页 → 改建页图库 → 页横幅。"""
    forbid = forbid or set()

    # 0) 全局提示文件（如拍卖会请柬T0）
    for key, hints in COVER_FILE_HINTS:
        if key not in name:
            continue
        for h in hints:
            url = resolve_hint_file(h)
            if url and url not in forbid:
                return url

    # 1) 邻近 File
    fn = nearby_file(wt, name)
    if fn:
        url = file_url(fn)
        if url and url not in forbid:
            return url

    # 2) 专题传送门 / 同名页
    stem = re.sub(r"[：:].*$", "", name).strip()
    cands = list(portals or [])
    cands += [
        f"碧蓝海事局{name}活动专题",
        f"碧蓝海事局{name.rstrip('！!')}活动专题",
        name,
        name.rstrip("！!"),
        stem,
        re.sub(r"[·・].*$", "", name).strip(),
    ]
    seen: set[str] = set()
    for cand in cands:
        if not cand or len(cand) < 2 or cand in seen:
            continue
        seen.add(cand)
        try:
            url = page_banner(cand, hint=name)
            if url and url not in forbid:
                return url
            # 专题页图库细选
            url = pick_from_filenames(page_images(cand), name, forbid=forbid)
            if url:
                return url
        except Exception:
            pass

    # 3) 改建公告图库（按活动名打分，避免全家共用第一张）
    if page_title:
        url = pick_from_filenames(page_images(page_title), name, forbid=forbid)
        if url:
            return url

    if page_ban and page_ban not in forbid:
        return page_ban
    return ""


def maint_from_title(title: str) -> datetime:
    m = TITLE_RE.match(title)
    assert m
    return make_dt(int(m["y"]), int(m["m"]), int(m["d"]), int(m["h"]), int(m["mi"]))


def maint_end_from_text(text: str, start: datetime) -> datetime:
    m = re.search(
        rf"{start.month}月{start.day}日\s*{start.hour}:\d{{2}}\s*[~～\-–—至到]\s*"
        rf"(?:{start.month}月{start.day}日\s*)?(?P<h>\d{{1,2}})[:：](?P<mi>\d{{2}})",
        text,
    )
    if m:
        return make_dt(start.year, start.month, start.day, int(m["h"]), int(m["mi"]))
    return start + timedelta(hours=5)


def parse_span(
    span: str,
    maint_start: datetime,
    maint_end: datetime,
    next_maint: datetime | None = None,
) -> tuple[datetime, datetime] | None:
    span = span.strip().replace(" ", "")
    y = maint_start.year

    def one_side(s: str, *, is_start: bool) -> datetime | None:
        s = s.strip()
        if "维护后" in s:
            return maint_end
        m_day = re.search(r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日", s)
        # 「7月30日维护」→ 当天 10:00（港区常规维护点）
        if m_day and re.search(r"维护", s):
            yy = int(m_day.group(1) or y)
            return make_dt(yy, int(m_day.group(2)), int(m_day.group(3)), 10, 0)
        if "维护前" in s or s.strip() in ("维护", "维护前"):
            # 无下一期改建时，估 +14 天（周常维护节奏），避免 end==start
            return next_maint or (maint_start + timedelta(days=14))
        m = re.search(
            r"(?:(20\d{2})年)?(\d{1,2})月(\d{1,2})日(?:\s*(\d{1,2})[:：](\d{2}))?",
            s,
        )
        if not m:
            return None
        yy = int(m.group(1) or y)
        hh = int(m.group(4) if m.group(4) is not None else (0 if is_start else 23))
        mi = int(m.group(5) if m.group(5) is not None else (0 if is_start else 59))
        return make_dt(yy, int(m.group(2)), int(m.group(3)), hh, mi)

    parts = re.split(r"[~～\-–—至到]+", span)
    if len(parts) < 2:
        return None
    start = one_side(parts[0], is_start=True)
    end = one_side(parts[1], is_start=False)
    if not start or not end:
        return None
    if end <= start:
        end = make_dt(end.year + 1, end.month, end.day, end.hour, end.minute)
    hours = (end - start).total_seconds() / 3600
    if hours < 1 or hours > 24 * 120:
        return None
    return start, end


def clean_name(name: str) -> str:
    name = re.sub(r"'{2,}", "", name)
    name = re.sub(r"\{\{[^}]+\}\}", "", name)
    name = re.sub(r"\[\[([^|\]]+\|)?([^\]]+)\]\]", r"\2", name)
    name = re.sub(r"<[^>]+>", "", name)
    name = re.sub(r"^活动", "", name)
    name = name.strip(" ：:·-—「」『』")
    return name[:32]


def al_category(label: str, name: str) -> str:
    blob = f"{label} {name}"
    if re.search(r"建造|祈愿建造", blob):
        return "gacha"
    if re.search(
        r"大型|复刻|海域|作战|EX|SP|档案|限界挑战|同盟|人形之旅|信标|META|怪谈纪实",
        blob,
    ):
        return "combat"
    if re.search(r"回礼|登录|签到|累计|巡游|巡演|竞拍|任务|联动|公益", blob):
        return "event"
    return "event"


def parse_page(title: str, next_title: str | None = None) -> list[dict]:
    wt = page_wikitext(title)
    # META 行需保留小图标模板以便抽角色名；其它模板可剥
    text_meta = wt
    text = re.sub(r"\{\{[^{}]+\}\}", " ", wt)
    text_plain = re.sub(r"\[\[(?:File|文件):[^\]]+\]\]", " ", text, flags=re.I)
    maint_start = maint_from_title(title)
    maint_end = maint_end_from_text(wt, maint_start)
    next_maint = (
        maint_from_title(next_title) if next_title and TITLE_RE.match(next_title) else None
    )
    portals = portal_pages(wt)
    out: list[dict] = []

    def push(name: str, label: str, span: str, *, category: str | None = None) -> None:
        name = clean_name(name)
        span = (span or "").strip()
        if not name or not span or SKIP.search(name):
            return
        if "活动专题" in name or name.startswith("{{"):
            return
        pair = parse_span(span, maint_start, maint_end, next_maint)
        if not pair:
            return
        start, end = pair
        if "维护前" in span and end <= start and next_maint:
            end = next_maint
        out.append(
            {
                "name": name,
                "label": label,
                "start": start,
                "end": end,
                "category": category or al_category(label, name),
                "page": title,
                "portals": portals,
                "wt": wt,
            }
        )

    for m in EVENT_RE.finditer(text_plain):
        push(
            m.group("name"),
            m.group("label"),
            m.group("span1") or m.group("span2") or "",
        )

    for m in META_RE.finditer(text_meta):
        ship = clean_name(m.group("name"))
        push(
            f"信标·META：{ship}" if ship else "信标·META",
            "信标·META",
            m.group("span"),
            category="combat",
        )

    for m in BUILD_RE.finditer(text_plain):
        if SKIP.search(m.group(0)):
            continue
        span = (m.group("span1") or m.group("span2") or "").strip()
        if not span:
            continue
        window = text_plain[max(0, m.start() - 80) : m.end() + 80]
        ships = re.findall(r"(?:「|『|\{\{小图标\|)([^」』|\n]{2,16})", window)
        push(
            "限时建造" + (f"·{ships[0]}" if ships else ""),
            "限时建造",
            span,
            category="gacha",
        )

    return out


def assign_banners(items: list[dict]) -> None:
    """统一配图并禁止 URL 复用。"""
    used: set[str] = set()
    # 先处理有强提示的（竞拍/限界/META），再处理其它
    def rank(e: dict) -> int:
        n = e.get("name") or ""
        for i, (key, _) in enumerate(COVER_FILE_HINTS):
            if key in n:
                return i
        return 99

    for e in sorted(items, key=rank):
        time.sleep(0.2)
        page_ban = ""
        try:
            page_ban = page_banner(e["page"], hint=e["name"])
        except Exception:
            page_ban = ""
        url = pick_event_banner(
            e["name"],
            e["page"],
            e.get("wt") or "",
            page_ban,
            forbid=used,
            portals=e.get("portals") or [],
        )
        if url:
            used.add(url)
        e["banner"] = url or ""


def self_check(events: list[dict], now: datetime) -> list[str]:
    issues: list[str] = []
    by_ban: dict[str, list[str]] = {}
    titles = " ".join(e.get("title") or "" for e in events)
    for key in ("限界挑战", "世界巡游", "自动步兵", "特别竞拍", "怪谈纪实"):
        if key not in titles:
            issues.append(f"可能漏抓：含「{key}」的进行中活动")
    if "信标" not in titles:
        issues.append("可能漏抓：信标·META（长线挑战）")

    for e in events:
        title = e.get("title") or ""
        try:
            s = datetime.fromisoformat(e["start"])
            en = datetime.fromisoformat(e["end"])
        except Exception:
            issues.append(f"坏时段：{title}")
            continue
        if en <= s:
            issues.append(f"结束≤开始：{title}")
        days = (en - s).total_seconds() / 86400
        if days > 120:
            issues.append(f"跨度过长({days:.0f}d)：{title}")
        if s <= now < en and e.get("status") != "进行中":
            issues.append(f"状态未刷新：{title} status={e.get('status')}")
        ban = e.get("banner") or ""
        if ban:
            by_ban.setdefault(ban, []).append(title)
        else:
            issues.append(f"无配图：{title}")
    for ban, ts in by_ban.items():
        if len(ts) > 1:
            issues.append(f"配图复用：{' / '.join(ts)}")
    return issues


def main() -> int:
    ref = now_cn()
    titles = list_rebuild_pages(ref.year)
    if ref.month <= 2:
        titles = list_rebuild_pages(ref.year - 1) + titles
    # 扫近 2 个月改建（含跨页长活动如世界巡游 / 信标）
    recent = titles[-18:]
    print(f"  扫描 {len(recent)} 篇港区改建")

    collected: list[dict] = []
    for title in recent:
        idx = titles.index(title) if title in titles else -1
        nxt = titles[idx + 1] if idx >= 0 and idx + 1 < len(titles) else None
        try:
            wt = page_wikitext(title)
            if len(wt) < 80:
                print(f"  {title}: (无页面)")
                continue
            items = parse_page(title, nxt)
            print(f"  {title}: {len(items)}")
            collected.extend(items)
        except Exception as e:
            print(f"  [skip] {title}: {e}")
        time.sleep(0.5)

    best: dict[str, dict] = {}
    for e in collected:
        k = f"{e['name']}|{e['start'].date()}"
        prev = best.get(k)
        if not prev or e["end"] > prev["end"]:
            best[k] = e

    live_items = [e for e in best.values() if e["end"] >= ref]
    print(f"  配图 {len(live_items)} 条…")
    assign_banners(live_items)

    events = []
    for e in live_items:
        banner = ""
        if e.get("banner"):
            banner = cache_cover(f"al-{e['name'][:16]}", e["banner"], LINK_BASE)
        page_q = urllib.parse.quote(e["page"])
        stem = re.sub(r"[^\w\u4e00-\u9fff]+", "", e["name"])[:18]
        events.append(
            build_event(
                cid=f"al-{stem}-{e['start'].strftime('%m%d')}",
                title=e["name"],
                header=f"{e['label']}·{e['name']}"[:40],
                banner=banner,
                link=LINK_BASE + page_q,
                start=e["start"],
                end=e["end"],
                summary=e["page"],
                category=e["category"],
            )
        )

    events.sort(key=lambda x: (x["category"] != "combat", x.get("start") or ""))
    issues = self_check(events, ref)
    for msg in issues:
        print(f"  [check] {msg}")

    out_path = DATA / "azurlane.json"
    if not events and out_path.exists():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
            if prev.get("events"):
                print("[azurlane] 本次抓取为空，保留上次数据（wiki 可能限流）")
                return 0
        except Exception:
            pass

    write_events(
        out_path,
        {
            "game": "碧蓝航线",
            "pending": False,
            "fetchedAt": ref.isoformat(),
            "count": len(events),
            "events": events,
            "source": "wiki.biligame.com/blhx 港区改建",
            "notes": issues[:20],
        },
    )
    print(f"[azurlane] {len(events)} 条进行中/预告 · 自检 {len(issues)} 项")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

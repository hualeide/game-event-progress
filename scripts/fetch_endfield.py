#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取终末地官网公告（RSC bulletins），解析可打活动 / 卡池时段。"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DATA,
    TZ,
    allow_fuzzy_estimate,
    build_event,
    cache_cover,
    http_get,
    is_bare_announce,
    make_dt,
    now_cn,
    parse_ranges,
    strip_html,
    write_events,
)

NEWS_URL = "https://endfield.hypergryph.com/news"
DETAIL_URL = "https://endfield.hypergryph.com/news/{cid}"

KEEP = re.compile(
    r"危机合约|重燃测试|挑战|丰碑|作战|活动开启|内容更新|版本更新|限时挑战|影拓|版本预|核心章节|"
    r"寻访|卡池|特许寻访|标准寻访",
    re.I,
)
SKIP = re.compile(
    r"封禁|支付|启动器|征集|创作|小红书|特卖|研发通讯|问卷|云·",
    re.I,
)

# 开放时间：2026/06/26 12:00（服务器时间） - 版本更新维护前
OPEN_UNTIL_MAINT = re.compile(
    r"(?:开放时间|活动时间)[：:]\s*"
    r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\s*(\d{1,2})[:：](\d{2})"
    r"[^\n]{0,40}?(?:版本更新维护前|下次版本更新维护前)"
)
# 开放时间：… \n · 寻访说明：「逐罪者」特许寻访
POOL_WITH_WHEN = re.compile(
    r"开放时间[：:]\s*(?P<when>[^\n]+)\s*"
    r"[^\n]{0,80}?"
    r"寻访说明[：:]\s*「(?P<name>[^」]{2,20})」特许寻访",
    re.S,
)
# 2026年7月16日06:00 / 2026/07/16 06:00
MAINT_AT = re.compile(
    r"(?:版本更新(?:停机)?维护|更新维护)[^\n]{0,40}?"
    r"(?:于\s*)?(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(\d{1,2})[:：](\d{2})"
    r"|"
    r"(?:版本更新(?:停机)?维护|更新维护)[^\n]{0,40}?"
    r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\s*(\d{1,2})[:：](\d{2})"
)
MAINT_AT2 = re.compile(
    r"计划将于\s*(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(\d{1,2})[:：](\d{2})"
)


def extract_bulletins(rsc_text: str) -> list[dict]:
    i = rsc_text.find('"bulletins":[')
    if i < 0:
        return []
    chunk = rsc_text[i : i + 120000]
    start = chunk.find("[")
    depth = 0
    end = None
    for j, ch in enumerate(chunk[start:], start):
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                end = j + 1
                break
    if end is None:
        return []
    return json.loads(chunk[start:end])


def fetch_list() -> list[dict]:
    body = http_get(
        NEWS_URL,
        {
            "Accept": "text/x-component",
            "RSC": "1",
            "Referer": "https://endfield.hypergryph.com/news",
        },
    ).decode("utf-8", "ignore")
    items = extract_bulletins(body)
    print(f"[EF] bulletins {len(items)}")
    return items


def fetch_detail_text(cid: str) -> str:
    """从 RSC 里抽公告正文，避免 unicode_escape 把中文弄坏。"""
    body = http_get(
        DETAIL_URL.format(cid=cid),
        {
            "Accept": "text/x-component",
            "RSC": "1",
            "Referer": "https://endfield.hypergryph.com/news",
        },
    ).decode("utf-8", "replace")
    chunks = re.findall(r"<p[\s\S]{0,80}?>[\s\S]{0,3000}?</p>", body)
    if chunks:
        return strip_html("\n".join(chunks))
    text = body.replace("\\n", "\n").replace('\\"', '"')
    text = text.replace("\\u003c", "<").replace("\\u003e", ">")
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    return strip_html(text)


def short_name(title: str) -> str:
    m = re.search(r"「([^」]+)」", title)
    if m:
        return m.group(1)[:28]
    return re.sub(r"说明|开启|更新", "", title).strip()[:28]


def is_playable(title: str) -> bool:
    if re.search(r"寻访|卡池", title):
        return True
    if is_bare_announce(title):
        return False
    if SKIP.search(title) and not re.search(r"危机合约|版本更新|版本预", title):
        return False
    if SKIP.search(title) and not KEEP.search(title):
        return False
    return bool(KEEP.search(title))


def find_next_maint(texts: list[str], now: datetime) -> datetime | None:
    cands: list[datetime] = []
    for text in texts:
        for m in MAINT_AT2.finditer(text):
            y, mo, d, h, mi = map(int, m.groups())
            cands.append(make_dt(y, mo, d, h, mi))
        for m in MAINT_AT.finditer(text):
            g = m.groups()
            if g[0]:
                y, mo, d, h, mi = map(int, g[:5])
            else:
                y, mo, d, h, mi = map(int, g[5:])
            cands.append(make_dt(y, mo, d, h, mi))
    future = [t for t in cands if t > now - timedelta(hours=6)]
    if future:
        return min(future)
    return min(cands) if cands else None


def parse_ef_ranges(text: str, now: datetime, next_maint: datetime | None) -> list[dict]:
    ranges = parse_ranges(text, now)
    for m in OPEN_UNTIL_MAINT.finditer(text):
        y, mo, d, h, mi = map(int, m.groups())
        start = make_dt(y, mo, d, h, mi)
        end = next_maint or (start + timedelta(days=21))
        if end <= start:
            end = start + timedelta(days=14)
        ranges.append(
            {
                "label": "开放至版本维护前",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "raw": m.group(0)[:80],
            }
        )
    return ranges


def pick_best_range(ranges: list[dict], now: datetime) -> dict | None:
    """优先进行中 → 即将开始 → 跨度最长。"""
    if not ranges:
        return None
    live, soon, rest = [], [], []
    for r in ranges:
        s = datetime.fromisoformat(r["start"])
        e = datetime.fromisoformat(r["end"])
        if (e - s).total_seconds() < 20 * 3600:
            continue
        if s <= now <= e:
            live.append(r)
        elif now < s:
            soon.append(r)
        else:
            rest.append(r)

    def span(r: dict) -> float:
        return (
            datetime.fromisoformat(r["end"]) - datetime.fromisoformat(r["start"])
        ).total_seconds()

    if live:
        return max(live, key=span)
    if soon:
        return min(soon, key=lambda r: datetime.fromisoformat(r["start"]))
    recent = [
        r for r in rest if datetime.fromisoformat(r["end"]) >= now - timedelta(days=2)
    ]
    if recent:
        return max(recent, key=span)
    return None


def ranges_from_when(when: str, now: datetime, next_maint: datetime | None) -> list[dict]:
    """解析单行开放时间文案。"""
    when = (when or "").strip()
    blob = f"开放时间：{when}"
    ranges = parse_ef_ranges(blob, now, next_maint)
    if ranges:
        return ranges
    # 「xxx」版本开启后 - 2026/06/26 11:59
    m = re.search(
        r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\s*(\d{1,2})[:：](\d{2})\s*$",
        when,
    )
    if m and ("开启后" in when or "更新后" in when):
        y, mo, d, h, mi = map(int, m.groups())
        end = make_dt(y, mo, d, h, mi)
        start = end - timedelta(days=14)
        return [
            {
                "label": "开放时间",
                "start": start.isoformat(),
                "end": end.isoformat(),
                "raw": when[:80],
            }
        ]
    return parse_ranges(blob, now)


def extract_named_gacha(
    text: str,
    *,
    now: datetime,
    next_maint: datetime | None,
    cover: str,
    source_cid: str,
) -> list[dict]:
    """从版本说明正文拆出特许寻访卡池。"""
    out: list[dict] = []
    seen: set[str] = set()
    for m in POOL_WITH_WHEN.finditer(text):
        name = m.group("name").strip()
        when = m.group("when").strip()
        if not name or name in seen:
            continue
        ranges = ranges_from_when(when, now, next_maint)
        primary = pick_best_range(ranges, now)
        if not primary:
            # 开放至维护前但未进 pick（跨度过滤等）时直接用
            if ranges:
                primary = ranges[0]
            else:
                continue
        start = datetime.fromisoformat(primary["start"])
        end = datetime.fromisoformat(primary["end"])
        if end < now - timedelta(days=2):
            continue
        seen.add(name)
        banner = (
            cache_cover(f"ef-gacha-{source_cid}-{name[:8]}", cover, NEWS_URL) if cover else ""
        )
        slug = re.sub(r"[^\w\u4e00-\u9fff]+", "", name)[:16]
        out.append(
            build_event(
                cid=f"{source_cid}-gacha-{slug}",
                title=f"「{name}」特许寻访",
                header=f"「{name}」",
                banner=banner,
                link=DETAIL_URL.format(cid=source_cid),
                start=start,
                end=end,
                ranges=ranges[:4] or [primary],
                kind="preview" if start > now else "live",
                fuzzy="维护前" in when or "维护前" in (primary.get("label") or ""),
                category="gacha",
                summary=f"特许寻访 · {name}",
            )
        )
    return out


def main() -> int:
    now = now_cn()
    items = fetch_list()
    events: list[dict] = []
    notes: list[str] = []
    detail_cache: dict[str, str] = {}

    # 先扫一遍找下次维护点（向渊行等）
    maint_texts: list[str] = []
    for it in items:
        title = (it.get("title") or "").strip()
        cid = str(it.get("cid") or "")
        if re.search(r"版本预|维护|更新预告|核心章节", title):
            t = fetch_detail_text(cid)
            detail_cache[cid] = t
            maint_texts.append(t)
            maint_texts.append(title)
    next_maint = find_next_maint(maint_texts, now)
    if next_maint:
        print(f"[EF] next maint ~ {next_maint.isoformat()}")

    for it in items:
        title = (it.get("title") or "").strip()
        cid = str(it.get("cid") or "")
        if not cid:
            continue
        if not is_playable(title):
            notes.append(f"{cid} 跳过：{title[:40]}")
            continue

        print(f"  [detail] {cid} {title[:40]}")
        text = detail_cache.get(cid) or fetch_detail_text(cid)
        detail_cache[cid] = text
        if len(text) < 80:
            text = strip_html(it.get("brief") or "") + "\n" + text

        cover = it.get("cover") or ""

        # 版本更新说明：拆出卡池（不把「维护前」时段污染整帖作战）
        if re.search(r"版本更新说明|内容说明", title):
            for gev in extract_named_gacha(
                text, now=now, next_maint=next_maint, cover=cover, source_cid=cid
            ):
                gname = re.sub(r"[「」]", "", gev.get("header") or "")
                # 已有同名专用寻访帖则跳过
                if any(
                    e.get("category") == "gacha"
                    and gname
                    and gname in (e.get("header") or e.get("title") or "")
                    for e in events
                ):
                    continue
                events.append(gev)
                print(f"  + gacha [{gev['status']}] {gev['header']} | {gev['remain']}")

        # 寻访帖才解析「至版本维护前」；作战帖只用普通时段
        if re.search(r"寻访|卡池", title):
            ranges = parse_ef_ranges(text, now, next_maint)
        else:
            ranges = parse_ranges(text, now)
        primary = pick_best_range(ranges, now)

        fuzzy = False
        if not primary:
            # 纯公告（预下载/内容更新说明等）不估起止
            if is_bare_announce(title) or (
                not re.search(r"寻访|卡池", title) and not allow_fuzzy_estimate(title)
            ):
                notes.append(f"{cid} 纯公告无时段，跳过：{title[:40]}")
                continue
            singles = re.findall(
                r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\s*(\d{1,2})[:：](\d{2})", text
            )
            if singles:
                y, m, d, h, mi = map(int, singles[0])
                start = datetime(y, m, d, h, mi, tzinfo=TZ)
            elif it.get("displayTime") and re.search(r"寻访|卡池", title):
                start = datetime.fromtimestamp(int(it["displayTime"]), tz=TZ)
            else:
                notes.append(f"{cid} 无时段：{title[:40]}")
                continue
            if re.search(r"寻访|卡池", title):
                end = next_maint or (start + timedelta(days=14))
                label = "估时（至版本维护前）" if next_maint else "估时（寻访）"
            else:
                end = start + timedelta(days=14)
                label = "估时（活动）"
            primary = {
                "label": label,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "raw": "single-node",
            }
            ranges = [primary]
            fuzzy = True

        start = datetime.fromisoformat(primary["start"])
        end = datetime.fromisoformat(primary["end"])
        if end < now - timedelta(days=2):
            notes.append(f"{cid} 已过期：{title[:40]}")
            # 版本说明里的卡池已在上面拆过，这里只跳过整帖
            continue

        banner = cache_cover(f"ef-{cid}", cover, "https://endfield.hypergryph.com/") if cover else ""
        name = short_name(title)
        cat = (
            "gacha"
            if re.search(r"寻访|卡池", title)
            else ("event" if re.search(r"签到|特卖|申领|预下载", title) else "combat")
        )
        # 专用寻访帖与版本拆条去重（同名保留专用帖）
        if cat == "gacha":
            events = [
                e
                for e in events
                if not (e.get("category") == "gacha" and name in (e.get("header") or e.get("title") or ""))
            ]
        ev = build_event(
            cid=cid,
            title=title,
            header=f"「{name}」",
            banner=banner,
            link=DETAIL_URL.format(cid=cid),
            start=start,
            end=end,
            ranges=ranges,
            kind="preview" if start > now else "live",
            fuzzy=fuzzy,
            category=cat,
            summary=(it.get("brief") or "")[:180],
        )
        if it.get("displayTime"):
            ev["updatedAt"] = datetime.fromtimestamp(int(it["displayTime"]), tz=TZ).isoformat()
        events.append(ev)
        print(f"  + [{ev['status']}] {name} · {cat} | {ev['remain']}")

    rank = {"进行中": 0, "即将开始": 1, "已结束": 2}
    events.sort(key=lambda e: (e.get("category") != "gacha", rank.get(e["status"], 9), e.get("start") or ""))

    payload = {
        "game": "终末地",
        "source": NEWS_URL,
        "fetchedAt": now.isoformat(),
        "timezone": "Asia/Shanghai",
        "count": len(events),
        "notes": notes[:40],
        "events": events,
    }
    if next_maint:
        payload["notes"] = [f"下次版本维护估：{next_maint.isoformat()}"] + payload["notes"]
    write_events(DATA / "endfield.json", payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

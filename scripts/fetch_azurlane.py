#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""浠庣ⅶ钃濊埅绾?Bwiki銆屾腐鍖烘敼寤恒€嶅叕鍛婅В鏋愰檺鏃舵椿鍔?/ 寤洪€犮€?""

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

TITLE_RE = re.compile(r"^(?P<y>20\d{2})骞??P<m>\d{1,2})鏈??P<d>\d{1,2})鏃??P<h>\d{1,2}):(?P<mi>\d{2})娓尯鏀瑰缓$")

# 寮€鍚檺鏃跺ぇ鍨嬫椿鍔?''澶嶅埢锛氱唤鏀句簬杈夊厜涔嬪煄'''锛屾椿鍔ㄦ椂闂?鏈?8鏃ョ淮鎶ゅ悗~6鏈?5鏃ョ淮鎶ゅ墠
# 寮€鍚檺鏃舵椿鍔ㄣ€岃繙鑸洖绀笺€嶏紙7鏈?鏃ョ淮鎶ゅ悗~7鏈?2鏃?3:59锛?
EVENT_RE = re.compile(
    r"(?P<label>寮€鍚檺鏃跺ぇ鍨嬫椿鍔▅寮€鍚檺鏃惰仈鍔ㄥ鍒绘椿鍔▅寮€鍚檺鏃惰仈鍔ㄦ椿鍔▅寮€鍚檺鏃跺鍒绘椿鍔▅"
    r"寮€鍚檺鏃剁壒娈婃椿鍔▅寮€鍚檺鏃舵椿鍔▅寮€鍚柊涓€鏈焲寮€鍚笅涓€鏈焲寮€鍚椿鍔▅澶嶅埢[锛?])\s*"
    r"[銆屻€嶾"]?(?P<name>[^銆嶃€廫"\n]{2,48}?)[銆嶃€廫"]?"
    r"(?:娲诲姩)?"
    r"(?:"
    r"[锛?]\s*娲诲姩鏃堕棿(?P<span1>[^銆俓n锛?]{6,80})"
    r"|"
    r"[锛?](?P<span2>[^锛?\n]{6,80})[锛?]"
    r")",
)

# 闄愭椂寤洪€犳湡闂?/ 寮€鍚檺鏃跺缓閫?
BUILD_RE = re.compile(
    r"(?P<label>闄愭椂寤洪€爘闄愭椂閲嶈繑寤洪€?"
    r"[^銆俓n]{0,60}?"
    r"(?:"
    r"娲诲姩鏃堕棿(?P<span1>[^銆俓n]{6,60})"
    r"|"
    r"[锛?](?P<span2>[^锛?\n]{6,60})[锛?]"
    r")",
)

# 銆岀鐮斻€嶄箣绫讳笉绠?
SKIP = re.compile(r"绀煎寘|鎹㈣鍟嗗簵|浼樻儬|鐮斿彂绀煎寘|鍏戞崲鍟嗗簵|瀹跺叿|鎶垫墸")


def wiki_json(params: dict, retries: int = 4) -> dict:
    q = urllib.parse.urlencode({**params, "format": "json"})
    url = f"{API}?{q}"
    last: Exception | None = None
    for i in range(retries):
        try:
            return http_get_json(url, UA)
        except HTTPError as e:
            last = e
            # 567 / 429 绛夐檺娴?
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
            {"action": "query", "list": "allpages", "apprefix": f"{year}骞?, "aplimit": "max"}
        ).get("query", {}).get("allpages", [])
        titles = [p["title"] for p in pages if "娓尯鏀瑰缓" in p["title"] and TITLE_RE.match(p["title"])]
    except Exception as e:
        print(f"  [warn] 鍒楄〃澶辫触锛屾敼鐢ㄦ湰鍦扮紦瀛? {e}")

    if CACHE.exists():
        for p in CACHE.glob("*.txt"):
            # 鏂囦欢鍚嶈繕鍘熶笉瀹屽叏锛岃棣栬鎴栫敤宸茬煡妯″紡鎵弿鐩綍鏃?metadata
            pass

    # 宸茬煡杩戞湡缁存姢锛坵iki 闄愭祦鏃跺厹搴曪級
    fallback = [
        f"{year}骞?鏈?8鏃?0:00娓尯鏀瑰缓",
        f"{year}骞?鏈?鏃?0:00娓尯鏀瑰缓",
        f"{year}骞?鏈?2鏃?0:00娓尯鏀瑰缓",
        f"{year}骞?鏈?8鏃?0:00娓尯鏀瑰缓",
        f"{year}骞?鏈?5鏃?0:00娓尯鏀瑰缓",
        f"{year}骞?鏈?鏃?0:00娓尯鏀瑰缓",
        f"{year}骞?鏈?6鏃?0:00娓尯鏀瑰缓",
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
    except Exception as e:
        if cached.exists() and cached.stat().st_size > 100:
            print(f"  [cache] {title}")
            return cached.read_text(encoding="utf-8")
        raise e
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    return ""


def page_banner(title: str) -> str:
    data = wiki_json({"action": "parse", "page": title, "prop": "images"})
    images = data.get("parse", {}).get("images") or []
    prefer = next((i for i in images if re.search(r"banner|Banner|娲诲姩|涓撻", i, re.I)), None)
    name = prefer or (images[0] if images else None)
    if not name:
        return ""
    info = wiki_json(
        {
            "action": "query",
            "titles": f"File:{name}",
            "prop": "imageinfo",
            "iiprop": "url",
        }
    )
    pages = info.get("query", {}).get("pages") or {}
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        return ii.get("url") or ""
    return ""


def maint_from_title(title: str) -> datetime:
    m = TITLE_RE.match(title)
    assert m
    return make_dt(int(m["y"]), int(m["m"]), int(m["d"]), int(m["h"]), int(m["mi"]))


def maint_end_from_text(text: str, start: datetime) -> datetime:
    m = re.search(
        rf"{start.month}鏈坽start.day}鏃s*{start.hour}:\d{{2}}\s*[~锝瀄-鈥撯€旇嚦鍒癩\s*"
        rf"(?:{start.month}鏈坽start.day}鏃s*)?(?P<h>\d{{1,2}})[:锛歖(?P<mi>\d{{2}})",
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
        if "缁存姢鍚? in s:
            return maint_end
        m_day = re.search(r"(?:(20\d{2})骞??(\d{1,2})鏈?\d{1,2})鏃?, s)
        # 銆?鏈?0鏃ョ淮鎶ゃ€嶁啋 褰撳ぉ 10:00锛堟腐鍖哄父瑙勭淮鎶ょ偣锛?
        if m_day and re.search(r"缁存姢", s):
            yy = int(m_day.group(1) or y)
            return make_dt(yy, int(m_day.group(2)), int(m_day.group(3)), 10, 0)
        if "缁存姢鍓? in s or s.strip() in ("缁存姢", "缁存姢鍓?):
            return next_maint or maint_start
        m = re.search(
            r"(?:(20\d{2})骞??(\d{1,2})鏈?\d{1,2})鏃??:\s*(\d{1,2})[:锛歖(\d{2}))?",
            s,
        )
        if not m:
            return None
        yy = int(m.group(1) or y)
        hh = int(m.group(4) if m.group(4) is not None else (0 if is_start else 23))
        mi = int(m.group(5) if m.group(5) is not None else (0 if is_start else 59))
        return make_dt(yy, int(m.group(2)), int(m.group(3)), hh, mi)

    parts = re.split(r"[~锝瀄-鈥撯€旇嚦鍒癩+", span)
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
    name = re.sub(r"^娲诲姩", "", name)
    name = name.strip(" 锛?路-鈥斻€屻€嶃€庛€?)
    return name[:32]


def al_category(label: str, name: str) -> str:
    blob = f"{label} {name}"
    if re.search(r"寤洪€爘绁堟効寤洪€?, blob):
        return "gacha"
    if re.search(r"澶у瀷|澶嶅埢|娴峰煙|浣滄垬|EX|SP|妗ｆ|闄愮晫鎸戞垬|鍚岀洘|浜哄舰涔嬫梾", blob):
        return "combat"
    if re.search(r"鍥炵ぜ|鐧诲綍|绛惧埌|绱|宸℃父|宸℃紨|绔炴媿|浠诲姟|鑱斿姩|鍏泭", blob):
        return "event"
    return "event"


def parse_page(title: str, next_title: str | None = None) -> list[dict]:
    wt = page_wikitext(title)
    text = re.sub(r"\{\{[^{}]+\}\}", " ", wt)
    text = re.sub(r"\[\[File:[^\]]+\]\]", " ", text)
    maint_start = maint_from_title(title)
    maint_end = maint_end_from_text(wt, maint_start)
    next_maint = maint_from_title(next_title) if next_title and TITLE_RE.match(next_title) else None
    out: list[dict] = []

    for m in EVENT_RE.finditer(text):
        name = clean_name(m.group("name"))
        span = (m.group("span") or "").strip()
        if not name or not span or SKIP.search(name):
            continue
        if "娲诲姩涓撻" in name or name.startswith("{{"):
            continue
        pair = parse_span(span, maint_start, maint_end, next_maint)
        if not pair:
            continue
        start, end = pair
        if "缁存姢鍓? in span and next_maint and end <= start:
            end = next_maint
        label = m.group("label")
        out.append(
            {
                "name": name,
                "label": label,
                "start": start,
                "end": end,
                "category": al_category(label, name),
                "page": title,
            }
        )

    for m in BUILD_RE.finditer(text):
        if SKIP.search(m.group(0)):
            continue
        span = (m.group("span") or "").strip()
        if not span:
            continue
        pair = parse_span(span, maint_start, maint_end, next_maint)
        if not pair:
            continue
        start, end = pair
        window = text[max(0, m.start() - 80) : m.end() + 80]
        ships = re.findall(r"(?:銆寍銆巪\{\{灏忓浘鏍嘰|)([^銆嶃€弢\n]{2,16})", window)
        name = "闄愭椂寤洪€? + (f"路{ships[0]}" if ships else "")
        out.append(
            {
                "name": name[:32],
                "label": "闄愭椂寤洪€?,
                "start": start,
                "end": end,
                "category": "gacha",
                "page": title,
            }
        )

    # 如果页面有"建造"但没被 BUILD_RE 捕获，用维护窗口推测建造活动
    if not out and ("建造" in text or "建" in text):
        build_pool = re.search(r"(?:建造|建).{0,30}?(?:活动时间|开放时间)[：: ]+([^。\n]{6,60})", text, re.S)
        if build_pool:
            pair = parse_span(build_pool.group(1), maint_start, maint_end, next_maint)
            if pair:
                start, end = pair
                name = "限时建造"
                out.append({
                    "name": name[:32],
                    "label": "限时建造",
                    "start": start,
                    "end": end,
                    "category": "gacha",
                    "page": title,
                })
        else:
            # 完全没找到建造时间范围，用维护窗口估时（约2周）
            est_start = maint_start
            est_end = maint_end + (maint_end - maint_start) if next_maint else maint_start + timedelta(days=14)
            out.append({
                "name": "限时建造（估时）",
                "label": "限时建造",
                "start": est_start,
                "end": est_end,
                "category": "gacha",
                "page": title,
            })

        if out:
        banner = ""
        try:
            banner = page_banner(title)
        except Exception:
            banner = ""
        for e in out:
            e["banner"] = banner
    return out


def main() -> int:
    ref = now_cn()
    titles = list_rebuild_pages(ref.year)
    if ref.month <= 2:
        titles = list_rebuild_pages(ref.year - 1) + titles
    # 浼樺厛鎵紦瀛橀綈鍏ㄧ殑杩戞湡椤碉紝鍑忓皯鏃犳晥璇锋眰
    recent = titles[-10:]
    print(f"  鎵弿 {len(recent)} 绡囨腐鍖烘敼寤?)

    collected: list[dict] = []
    for i, title in enumerate(recent):
        idx = titles.index(title) if title in titles else -1
        nxt = titles[idx + 1] if idx >= 0 and idx + 1 < len(titles) else None
        try:
            items = parse_page(title, nxt)
            print(f"  {title}: {len(items)}")
            collected.extend(items)
        except Exception as e:
            print(f"  [skip] {title}: {e}")
        time.sleep(0.7)

    best: dict[str, dict] = {}
    for e in collected:
        k = f"{e['name']}|{e['start'].date()}"
        prev = best.get(k)
        if not prev or e["end"] > prev["end"]:
            best[k] = e

    events = []
    for e in best.values():
        if e["end"] < ref:
            continue
        banner = ""
        if e.get("banner"):
            banner = cache_cover(f"al-{e['name'][:16]}", e["banner"], LINK_BASE)
        page_q = urllib.parse.quote(e["page"])
        stem = re.sub(r"[^\w\u4e00-\u9fff]+", "", e["name"])[:18]
        events.append(
            build_event(
                cid=f"al-{stem}-{e['start'].strftime('%m%d')}",
                title=e["name"],
                header=f"{e['label']}路{e['name']}"[:40],
                banner=banner,
                link=LINK_BASE + page_q,
                start=e["start"],
                end=e["end"],
                summary=e["page"],
                category=e["category"],
            )
        )

    events.sort(key=lambda x: (x["category"] != "combat", x.get("start") or ""))
    out_path = DATA / "azurlane.json"
    if not events and out_path.exists():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
            if prev.get("events"):
                print("[azurlane] 鏈鎶撳彇涓虹┖锛屼繚鐣欎笂娆℃暟鎹紙wiki 鍙兘闄愭祦锛?)
                return 0
        except Exception:
            pass

    write_events(
        out_path,
        {
            "game": "纰ц摑鑸嚎",
            "pending": False,
            "fetchedAt": ref.isoformat(),
            "count": len(events),
            "events": events,
            "source": "wiki.biligame.com/blhx 娓尯鏀瑰缓",
        },
    )
    print(f"[azurlane] {len(events)} 鏉¤繘琛屼腑/棰勫憡")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())




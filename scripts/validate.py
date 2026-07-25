#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化数据质量验证 + 修复建议生成器。

设计目标：
  发现模式 → 写成规则 → 自动检测 → 自动修复（可选）

运行方式：
  python scripts/validate.py              # 只检查，输出报告
  python scripts/validate.py --fix        # 检查 + 自动修复可修复项
  python scripts/validate.py --report     # 只输出人类可读中文报告
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PUBLIC_DATA = ROOT / "public" / "data"


# ============================================================
# 规则系统 — 发现新模式就往这里加
# ============================================================

# 类别纠错规则：如果标题/header含这些关键词 → 应改为指定类别
# 格式: (关键词列表, 正确类别, 说明)
CORRECT_CATEGORY_RULES: list[tuple[list[str], str, str]] = [
    # 原神/星铁/绝区零 — OST / 音乐
    (["OST", "主题曲", "主题歌", "主题OST", "原声", "主题音乐", "EP", "BGM", "专辑", "单曲", "原声带"], "event", "音乐/OST 不是作战"),
    # 壁纸 / 皮肤 / 家具
    (["壁纸", "名片", "名片纹饰", "头像框", "摆设", "家具", "家园", "尘歌壶", "换装", "外观"], "event", "装饰/外观类不是作战"),
    # 签到 / 登录
    (["签到", "登录奖励", "每日签到", "累计登录"], "event", "签到类不是作战"),
    # 兑换 / 商店
    (["兑换商店", "兑换码", "礼包兑换", "特卖"], "event", "兑换/商店类不是作战"),
    # 网页活动
    (["网页活动", "H5活动", "专题页", "官网活动", "浏览器活动", "外链活动"], "web", "网页活动"),
    # 创作 / 征集
    (["创作", "征集", "应援", "周边"], "event", "创作/征集不是作战"),
    # 维护 / 更新
    (["维护", "更新公告", "闪断更新", "版本更新"], "event", "维护公告不是作战"),
]

# 应当有卡池的游戏 — 如果抓取结果无卡池则告警
EXPECT_GACHA_GAMES: set[str] = {
    "events",       # 明日方舟
    "genshin",
    "starrail",
    "zzz",
    "wuwa",
    "bluearchive",
    "endfield",
    "azurlane",
    "nikke",
    "reverse1999",
    "gfl2",
    "hearthstone",
    "naraka",
}

# 应当有作战活动的游戏
EXPECT_COMBAT_GAMES: set[str] = {
    "events",
    "genshin",
    "starrail",
    "zzz",
    "wuwa",
    "bluearchive",
    "azurlane",
    "nikke",
    "reverse1999",
    "ptn",
    "snowbreak",
    "gfl2",
    "hearthstone",
    "pvz2",
    "naraka",
    "delta",
    "endfield",
}

# 类别分布异常阈值：单类别占比超过此值则告警
CATEGORY_DOMINANCE_THRESHOLD = 0.65

# ============================================================
# 验证逻辑
# ============================================================


def load_all_data() -> dict[str, dict[str, Any]]:
    """加载 data/ 下所有游戏数据 JSON"""
    result: dict[str, dict[str, Any]] = {}
    for p in sorted(DATA.glob("*.json")):
        if p.name in ("games-meta.json", "status.json", "audit-report.json", "fetch-summary.json", "delta.json"):
            continue
        if p.name.startswith("_"):
            continue
        if p.name.endswith("-summary.json") or p.name.endswith("-server.log"):
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8-sig"))
            if isinstance(d, dict) and "events" in d:
                result[p.stem] = d
        except Exception:
            pass
    return result


def check_category_misclassification(data: dict[str, dict]) -> list[dict]:
    """
    检查每个事件的类别是否与标题内容矛盾。
    例如标题含"OST"但类别是"combat" → 应改为"event"
    """
    findings: list[dict] = []
    for game_id, d in data.items():
        game_name = d.get("game", game_id)
        for ev in (d.get("events") or []):
            title = ev.get("title") or ""
            header = ev.get("header") or ""
            blob = f"{title} {header}"
            current_cat = ev.get("category") or ""

            for keywords, correct_cat, reason in CORRECT_CATEGORY_RULES:
                if current_cat == correct_cat:
                    continue  # 已经是对的
                for kw in keywords:
                    if kw in blob:
                        findings.append({
                            "game": game_id,
                            "game_name": game_name,
                            "event_id": ev.get("id", ""),
                            "title": title[:40],
                            "current_category": current_cat,
                            "correct_category": correct_cat,
                            "keyword": kw,
                            "reason": reason,
                            "fixable": True,
                            "fix": {
                                "field": "category",
                                "old_value": current_cat,
                                "new_value": correct_cat,
                            },
                        })
                        break
                # 每事件只报第一个匹配
                if findings and findings[-1]["event_id"] == ev.get("id", ""):
                    break
    return findings


def check_category_dominance(data: dict[str, dict]) -> list[dict]:
    """检查类别分布是否过于单一（某类占比 > 阈值）"""
    findings: list[dict] = []
    for game_id, d in data.items():
        game_name = d.get("game", game_id)
        evs = d.get("events") or []
        if len(evs) < 3:
            continue
        cats = Counter(e.get("category", "?") for e in evs if e.get("hasSchedule"))
        total = sum(cats.values())
        if total < 3:
            continue
        for cat, count in cats.most_common(1):
            ratio = count / total
            if ratio > CATEGORY_DOMINANCE_THRESHOLD:
                findings.append({
                    "game": game_id,
                    "game_name": game_name,
                    "total_events": total,
                    "dominant_category": cat,
                    "dominant_count": count,
                    "ratio": round(ratio, 3),
                    "threshold": CATEGORY_DOMINANCE_THRESHOLD,
                })
    return findings


def check_missing_categories(data: dict[str, dict]) -> list[dict]:
    """检查应该包含某类别的游戏是否缺失"""
    findings: list[dict] = []
    for game_id, d in data.items():
        game_name = d.get("game", game_id)
        evs = d.get("events") or []
        cats = set(e.get("category", "?") for e in evs if e.get("hasSchedule"))

        if game_id in EXPECT_GACHA_GAMES and "gacha" not in cats and len(evs) >= 2:
            findings.append({
                "game": game_id,
                "game_name": game_name,
                "missing": "gacha",
                "detail": f"有 {len(evs)} 个事件但无卡池活动，可能漏抓",
            })

        if game_id in EXPECT_COMBAT_GAMES and "combat" not in cats and len(evs) >= 2:
            findings.append({
                "game": game_id,
                "game_name": game_name,
                "missing": "combat",
                "detail": f"有 {len(evs)} 个事件但无作战活动，可能漏抓",
            })
    return findings


def check_fuzzy_events(data: dict[str, dict]) -> list[dict]:
    """检查模糊事件是否过多（依赖估算时间的活动）"""
    findings: list[dict] = []
    for game_id, d in data.items():
        game_name = d.get("game", game_id)
        evs = d.get("events") or []
        fuzzy_count = sum(1 for e in evs if e.get("fuzzy"))
        total = len(evs)
        if total >= 3 and fuzzy_count / total > 0.5:
            findings.append({
                "game": game_id,
                "game_name": game_name,
                "fuzzy_count": fuzzy_count,
                "total": total,
                "ratio": round(fuzzy_count / total, 2),
                "detail": f"超过半数是模糊时间（估算），建议优化爬虫",
            })
    return findings


def check_schedule_health(data: dict[str, dict]) -> list[dict]:
    """检查时间范围合理性"""
    findings: list[dict] = []
    now = datetime.now().astimezone()
    for game_id, d in data.items():
        game_name = d.get("game", game_id)
        for ev in (d.get("events") or []):
            if not ev.get("hasSchedule"):
                continue
            try:
                end = datetime.fromisoformat(str(ev["end"]))
                start = datetime.fromisoformat(str(ev["start"]))
            except Exception:
                continue
            duration = (end - start).total_seconds() / 86400
            if duration > 120:
                findings.append({
                    "game": game_id,
                    "game_name": game_name,
                    "event": ev.get("title", "")[:30],
                    "issue": f"活动跨度 {duration:.0f} 天，可能是常驻说明被误抓",
                    "severity": "warning",
                })
            if duration < 0.1:
                findings.append({
                    "game": game_id,
                    "game_name": game_name,
                    "event": ev.get("title", "")[:30],
                    "issue": f"活动仅 {(duration*24):.0f} 小时，可能有误",
                    "severity": "warning",
                })
    return findings


# ============================================================
# 修复执行
# ============================================================


def apply_fixes(data: dict[str, dict], findings: list[dict]) -> int:
    """自动应用可修复的发现项，返回修复数量"""
    fixed = 0
    for f in findings:
        if not f.get("fixable") or not f.get("fix"):
            continue
        game_id = f["game"]
        event_id = f["event_id"]
        if game_id not in data:
            continue
        for ev in data[game_id].get("events", []):
            if str(ev.get("id", "")) != event_id:
                continue
            fix = f["fix"]
            field = fix.get("field", "")
            new_val = fix.get("new_value")
            if field and new_val and ev.get(field) != new_val:
                old = ev.get(field)
                ev[field] = new_val
                print(f"  [fix] {game_id}/{event_id}: {field} '{old}' → '{new_val}'")
                fixed += 1
            break
    return fixed


# ============================================================
# 报告生成
# ============================================================


def generate_report(
    data: dict[str, dict],
    misclass: list[dict],
    dominance: list[dict],
    missing: list[dict],
    fuzzy: list[dict],
    schedule: list[dict],
    fixed_count: int = 0,
) -> str:
    """生成人类可读的中文报告"""
    lines: list[str] = []

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"{'='*60}")
    lines.append(f"  数据质量验证报告")
    lines.append(f"  生成时间：{now}")
    lines.append(f"{'='*60}")
    lines.append("")

    total_events = sum(len(d.get("events", [])) for d in data.values())
    lines.append(f"检查了 {len(data)} 个游戏，共 {total_events} 个事件")
    lines.append("")

    if fixed_count > 0:
        lines.append(f"  [OK] 自动修复 {fixed_count} 项")
        lines.append("")

    # 1. 类别误分类
    if misclass:
        lines.append(f"*  类别误分类 ({len(misclass)} 项)")
        lines.append("-" * 40)
        for f in misclass[:15]:
            lines.append(f"  {f['game_name']:>8s} | {f['title'][:28]:28s}")
            lines.append(f"          当前: {f['current_category']} → 应为: {f['correct_category']}")
            lines.append(f"          触发关键词: 「{f['keyword']}」({f['reason']})")
        if len(misclass) > 15:
            lines.append(f"  ... 还有 {len(misclass) - 15} 项")
        lines.append("")
        lines.append("  自动修复: python scripts/validate.py --fix")
        lines.append("")

    # 2. 类别分布异常
    if dominance:
        lines.append(f"*  类别分布异常 ({len(dominance)} 项)")
        lines.append("-" * 40)
        for f in dominance:
            lines.append(f"  {f['game_name']:>8s} | {f['dominant_category']} 占 {f['ratio']*100:.0f}%")
            lines.append(f"         ({f['dominant_count']}/{f['total_events']} 个事件)")
            lines.append(f"         建议检查是否误分类")
        lines.append("")

    # 3. 缺失类别
    if missing:
        lines.append(f"!  缺失预期类别 ({len(missing)} 项)")
        lines.append("-" * 40)
        for f in missing:
            lines.append(f"  {f['game_name']:>8s} | 缺少 {f['missing']} 类 | {f['detail']}")
        lines.append("")

    # 4. 模糊事件过多
    if fuzzy:
        lines.append(f"~  模糊事件过多 ({len(fuzzy)} 项)")
        lines.append("-" * 40)
        for f in fuzzy:
            lines.append(f"  {f['game_name']:>8s} | {f['fuzzy_count']}/{f['total']} ({f['ratio']*100:.0f}%) 是估时")
        lines.append("")

    # 5. 时间健康
    if schedule:
        lines.append(f"?  时间异常 ({len(schedule)} 项)")
        lines.append("-" * 40)
        for f in schedule:
            lines.append(f"  {f['game_name']:>8s} | {f['event'][:24]:24s} | {f['issue']}")
        lines.append("")

    # 汇总
    total_issues = len(misclass) + len(dominance) + len(missing) + len(fuzzy) + len(schedule)
    if total_issues == 0:
        lines.append("[OK] 全部检查通过，无异常")
    else:
        lines.append(f"{'='*60}")
        lines.append(f"  汇总：{total_issues} 项（可自动修复 {len([f for f in misclass if f.get('fixable')])} 项）")
        lines.append(f"{'='*60}")

    return "\n".join(lines)


# ============================================================
# 主入口
# ============================================================


def main() -> int:
    do_fix = "--fix" in sys.argv
    do_report = "--report" in sys.argv

    data = load_all_data()

    print(f"加载 {len(data)} 个游戏的数据文件")
    print()

    # 运行所有检查
    misclass = check_category_misclassification(data)
    print(f"类别误分类: {len(misclass)}")
    for f in misclass:
        print(f"  [{f['game']}] {f['title'][:30]:30s} {f['current_category']} → {f['correct_category']} (关键词: {f['keyword']})")

    dominance = check_category_dominance(data)
    print(f"\n类别分布异常: {len(dominance)}")

    missing = check_missing_categories(data)
    print(f"缺失类别: {len(missing)}")

    fuzzy_issues = check_fuzzy_events(data)
    print(f"模糊事件过多: {len(fuzzy_issues)}")

    schedule_issues = check_schedule_health(data)
    print(f"时间异常: {len(schedule_issues)}")

    # 修复
    fixed_count = 0
    if do_fix and misclass:
        print(f"\n--- 自动修复 ---")
        fixed_count = apply_fixes(data, misclass)
        # 写回文件
        for game_id, d in data.items():
            path = DATA / f"{game_id}.json"
            if path.exists():
                d["count"] = len(d.get("events", []))
                path.write_text(
                    json.dumps(d, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        print(f"\n修复 {fixed_count} 项，已写入 data/ 目录")
        print("请检查后提交: git add data/ && git commit -m 'fix: auto-correct event categories'")

    # 报告
    if do_report or not do_fix:
        report = generate_report(
            data, misclass, dominance, missing, fuzzy_issues, schedule_issues, fixed_count
        )
        print(f"\n\n{report}")

    # 退出码：有可修复误分类时返回非0
    total_issues = len(misclass) + len(dominance) + len(missing) + len(fuzzy_issues) + len(schedule_issues)
    return 1 if total_issues > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())


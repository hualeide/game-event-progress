#!/usr/bin/env python3
"""结束瞬间：now>=end 为已结束。纯函数，虚构带时区时间。"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

import common
import fetch_arknights as ark

TZ = common.TZ
START = datetime(2026, 7, 1, 12, 0, tzinfo=TZ)
END = datetime(2026, 7, 10, 4, 0, tzinfo=TZ)
BEFORE = START - timedelta(days=2)
AT_START = START
BEFORE_END = END - timedelta(microseconds=1)
AFTER = END + timedelta(microseconds=1)
RANGES = [{"label": "活动时间", "start": START.isoformat(), "end": END.isoformat()}]


class CommonBoundaryTests(unittest.TestCase):
    def test_timeline(self):
        self.assertEqual(common.status_of(START, END, BEFORE), "即将开始")
        self.assertEqual(common.progress_of(START, END, BEFORE), 0.0)
        self.assertNotEqual(common.remain_text(START, END, BEFORE), "已结束")

        self.assertEqual(common.status_of(START, END, AT_START), "进行中")
        self.assertEqual(common.progress_of(START, END, AT_START), 0.0)

        self.assertEqual(common.status_of(START, END, BEFORE_END), "进行中")
        self.assertNotEqual(common.remain_text(START, END, BEFORE_END), "已结束")
        self.assertLess(common.progress_of(START, END, BEFORE_END), 100.0)

        for now in (END, AFTER):
            self.assertEqual(common.status_of(START, END, now), "已结束")
            self.assertEqual(common.remain_text(START, END, now), "已结束")
            self.assertEqual(common.progress_of(START, END, now), 100.0)

    def test_missing_stays_unknown(self):
        now = END
        self.assertEqual(common.status_of(None, None, now), "未知")
        self.assertEqual(common.status_of(START, None, now), "未知")
        self.assertEqual(common.status_of(None, END, now), "未知")

    def test_build_event_at_end(self):
        with patch("common.now_cn", return_value=END):
            ev = common.build_event(
                cid="fake",
                title="虚构活动",
                header="虚构标题",
                banner="",
                link="https://example.test/event",
                start=START,
                end=END,
                ranges=RANGES,
            )
        self.assertEqual(ev["status"], "已结束")
        self.assertEqual(ev["kind"], "done")
        self.assertEqual(ev["progress"], 100.0)
        self.assertEqual(ev["remain"], "已结束")
        self.assertEqual(ev["start"], START.isoformat())
        self.assertEqual(ev["end"], END.isoformat())
        self.assertEqual(ev["allRanges"], RANGES)


class ArkBoundaryTests(unittest.TestCase):
    def test_timeline(self):
        self.assertEqual(ark.status_of(START, END, BEFORE), "即将开始")
        self.assertEqual(ark.progress_pct(START, END, BEFORE), 0.0)
        self.assertNotEqual(ark.remain_text(START, END, BEFORE), "已结束")

        self.assertEqual(ark.status_of(START, END, AT_START), "进行中")
        self.assertEqual(ark.progress_pct(START, END, AT_START), 0.0)

        self.assertEqual(ark.status_of(START, END, BEFORE_END), "进行中")
        self.assertNotEqual(ark.remain_text(START, END, BEFORE_END), "已结束")

        for now in (END, AFTER):
            self.assertEqual(ark.status_of(START, END, now), "已结束")
            self.assertEqual(ark.remain_text(START, END, now), "已结束")
            self.assertEqual(ark.progress_pct(START, END, now), 100.0)
            days = ark.day_span(START, END, now)
            self.assertEqual(days["remainDays"], 0)
            self.assertEqual(days["elapsedDays"], days["totalDays"])

    def test_end_only_and_missing(self):
        self.assertEqual(ark.status_of(None, END, BEFORE_END), "进行中")
        self.assertNotEqual(ark.remain_text(None, END, BEFORE_END), "已结束")
        self.assertEqual(ark.status_of(None, END, END), "已结束")
        self.assertEqual(ark.remain_text(None, END, END), "已结束")
        self.assertEqual(ark.status_of(None, END, AFTER), "已结束")
        self.assertEqual(ark.status_of(None, None, END), "进行中")
        self.assertEqual(ark.remain_text(None, None, END), "时间未知")
        self.assertEqual(ark.status_of(START, None, BEFORE), "即将开始")
        self.assertEqual(ark.status_of(START, None, AT_START), "进行中")


if __name__ == "__main__":
    unittest.main()

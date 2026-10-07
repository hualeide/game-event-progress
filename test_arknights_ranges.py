#!/usr/bin/env python3
"""方舟独立 parse_ranges / parse_gacha_pools。只喂虚构文本。"""

import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from fetch_arknights import TZ, parse_gacha_pools, parse_ranges, pick_primary

REF = datetime(2026, 7, 15, 12, tzinfo=TZ)


def pairs(text: str):
    return [(r["start"][:19], r["end"][:19], r["label"]) for r in parse_ranges(text, REF)]


class ArknightsRangeTests(unittest.TestCase):
    def test_bad_segment_keeps_later_good(self):
        samples = (
            (
                "活动时间：02月30日12:00 - 03月05日04:00\n活动时间：07月16日12:00 - 07月20日04:00",
                [("2026-07-16T12:00:00", "2026-07-20T04:00:00", "活动时间")],
            ),
            (
                "活动时间：07月16日25:00 - 07月20日04:00\n活动时间：08月01日10:00 - 08月03日04:00",
                [("2026-08-01T10:00:00", "2026-08-03T04:00:00", "活动时间")],
            ),
            (
                "02月30日12:00 - 03月05日04:00\n07月16日12:00 - 07月20日04:00",
                [("2026-07-16T12:00:00", "2026-07-20T04:00:00", "时段")],
            ),
            (
                "07月16日12:99 - 07月20日04:00 08月01日10:00 - 08月03日04:00",
                [("2026-08-01T10:00:00", "2026-08-03T04:00:00", "时段")],
            ),
            (
                "活动结束时间：2026年02月30日18:00\n活动时间：07月16日12:00 - 07月20日04:00",
                [("2026-07-16T12:00:00", "2026-07-20T04:00:00", "活动时间")],
            ),
            (
                "活动结束时间：2026年07月20日18:99\n活动时间：07月16日12:00 - 07月20日04:00",
                [("2026-07-16T12:00:00", "2026-07-20T04:00:00", "活动时间")],
            ),
        )
        for text, expect in samples:
            with self.subTest(text=text):
                self.assertEqual(pairs(text), expect)

    def test_historical_year_once(self):
        samples = (
            ("活动时间：2025年7月10日12:00 - 7月24日03:59", "2025-07-10T12:00:00", "2025-07-24T03:59:00"),
            ("活动时间：2024年3月1日10:00 - 3月8日04:00", "2024-03-01T10:00:00", "2024-03-08T04:00:00"),
        )
        for text, start, end in samples:
            with self.subTest(text=text):
                got = pairs(text)
                self.assertEqual(got, [(start, end, "活动时间")])

    def test_cross_year_and_explicit_reverse(self):
        self.assertEqual(
            pairs("活动时间：2025年12月25日12:00 - 2026年1月5日04:00"),
            [("2025-12-25T12:00:00", "2026-01-05T04:00:00", "活动时间")],
        )
        self.assertEqual(
            pairs("活动时间：2026年12月25日12:00 - 1月5日04:00"),
            [("2026-12-25T12:00:00", "2027-01-05T04:00:00", "活动时间")],
        )
        self.assertEqual(pairs("活动时间：2026年12月25日12:00 - 2026年1月5日04:00"), [])
        self.assertEqual(pairs("活动时间：2026年7月24日12:00 - 2025年7月10日03:59"), [])

    def test_same_line_keeps_independent_yearless(self):
        explicit = "活动时间：2025年7月10日12:00 - 2025年7月24日03:59"
        yearless = "开放时间：8月1日10:00 - 8月5日04:00"
        expect = {
            ("2025-07-10T12:00:00", "2025-07-24T03:59:00", "活动时间"),
            ("2026-08-01T10:00:00", "2026-08-05T04:00:00", "开放时间"),
        }
        for text in (
            explicit + "；" + yearless,
            explicit + " " + yearless,
            yearless + "；" + explicit,
            yearless + " " + explicit,
        ):
            with self.subTest(text=text):
                self.assertEqual(set(pairs(text)), expect)

    def test_bad_explicit_does_not_invent_yearless(self):
        bad = "活动时间：2025年2月30日12:00 - 3月5日04:00"
        good = "开放时间：8月1日10:00 - 8月5日04:00"
        expect = [("2026-08-01T10:00:00", "2026-08-05T04:00:00", "开放时间")]
        for text in (bad + "；" + good, bad + " " + good, good + "；" + bad, good + " " + bad):
            with self.subTest(text=text):
                self.assertEqual(pairs(text), expect)
        self.assertEqual(
            pairs("活动时间：2025年7月10日25:00 - 7月24日03:59；开放时间：8月1日10:00 - 8月5日04:00"),
            expect,
        )

    def test_exact_label_and_pick_primary(self):
        text = "关卡开放时间：8月1日10:00 - 8月20日04:00\n活动时间：7月16日12:00 - 7月18日04:00"
        got = parse_ranges(text, REF)
        self.assertEqual({r["label"] for r in got}, {"关卡开放时间", "活动时间"})
        primary = pick_primary(got)
        self.assertEqual(primary["label"], "活动时间")
        self.assertTrue(primary["start"].startswith("2026-07-16T12:00:00"))
        bare = "7月16日12:00 - 7月16日12:30"
        self.assertEqual(parse_ranges(bare, REF), [])
        long_bare = "1月1日00:00 - 6月1日00:00"
        self.assertEqual(parse_ranges(long_bare, REF), [])
        labeled_long = "活动时间：1月1日00:00 - 6月1日00:00"
        self.assertEqual(len(parse_ranges(labeled_long, REF)), 1)
        self.assertEqual(parse_ranges(labeled_long, REF)[0]["label"], "活动时间")

    def test_numbered_label_keeps_digit(self):
        text = "1阶段开放时间：8月1日10:00 - 8月5日04:00"
        got = parse_ranges(text, REF)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["label"], "1阶段开放时间")
        self.assertTrue(got[0]["start"].startswith("2026-08-01T10:00:00"))
        self.assertTrue(got[0]["end"].startswith("2026-08-05T04:00:00"))

    def test_unlabeled_explicit_year_not_downgraded(self):
        hist = parse_ranges("2025年7月10日12:00 - 7月24日03:59", REF)
        self.assertEqual(
            [(r["start"][:19], r["end"][:19]) for r in hist],
            [("2025-07-10T12:00:00", "2025-07-24T03:59:00")],
        )
        cross = parse_ranges("2025年12月25日12:00 - 2026年1月5日04:00", REF)
        self.assertEqual(
            [(r["start"][:19], r["end"][:19]) for r in cross],
            [("2025-12-25T12:00:00", "2026-01-05T04:00:00")],
        )
        omitted = parse_ranges("2026年12月25日12:00 - 1月5日04:00", REF)
        self.assertEqual(
            [(r["start"][:19], r["end"][:19]) for r in omitted],
            [("2026-12-25T12:00:00", "2027-01-05T04:00:00")],
        )
        self.assertEqual(parse_ranges("2025年2月30日12:00 - 3月5日04:00", REF), [])
        self.assertEqual(parse_ranges("2025年7月10日25:00 - 7月24日03:59", REF), [])

    def test_deadline_still_uses_ref_start(self):
        got = parse_ranges("活动结束时间：2026年7月31日23:59", REF)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["label"], "活动时间")
        self.assertTrue(got[0]["start"].startswith("2026-07-15T12:00:00"))
        self.assertTrue(got[0]["end"].startswith("2026-07-31T23:59:00"))


class ArknightsGachaTests(unittest.TestCase):
    def test_bad_pool_does_not_block_others(self):
        text = (
            "【能天使】限时寻访\n活动时间：07月16日25:00 - 07月20日04:00\n"
            "【银灰】限时寻访\n活动时间：07月16日12:00 - 07月24日03:59\n"
            "【星熊】限时寻访\n活动时间：02月30日12:00 - 03月05日04:00\n"
        )
        pools = parse_gacha_pools(text, REF)
        self.assertEqual([p["name"] for p in pools], ["银灰"])
        self.assertTrue(pools[0]["primary"]["start"].startswith("2026-07-16T12:00:00"))
        self.assertTrue(pools[0]["primary"]["end"].startswith("2026-07-24T03:59:00"))

    def test_same_name_skips_bad_keeps_good(self):
        bad_then_good = (
            "【星熊】限时寻访\n活动时间：02月30日12:00 - 03月05日04:00\n"
            "【星熊】限时寻访\n活动时间：08月01日12:00 - 08月10日03:59\n"
        )
        pools = parse_gacha_pools(bad_then_good, REF)
        self.assertEqual([p["name"] for p in pools], ["星熊"])
        self.assertTrue(pools[0]["primary"]["start"].startswith("2026-08-01T12:00:00"))

        good_then_bad = (
            "【星熊】限时寻访\n活动时间：08月01日12:00 - 08月10日03:59\n"
            "【星熊】限时寻访\n活动时间：07月16日12:99 - 07月20日04:00\n"
        )
        pools = parse_gacha_pools(good_then_bad, REF)
        self.assertEqual(len(pools), 1)
        self.assertTrue(pools[0]["primary"]["start"].startswith("2026-08-01T12:00:00"))
        self.assertTrue(pools[0]["primary"]["end"].startswith("2026-08-10T03:59:00"))

    def test_reverse_and_zero_rejected(self):
        reverse = "【FakePool】限时寻访 活动时间：8月1日16:00 - 8月1日12:00"
        zero = "【FakePool】限时寻访 活动时间：8月1日12:00 - 8月1日12:00"
        self.assertEqual(parse_gacha_pools(reverse, REF), [])
        self.assertEqual(parse_gacha_pools(zero, REF), [])

    def test_bad_same_name_does_not_block_later_good(self):
        text = (
            "【FakePool】限时寻访 活动时间：8月1日16:00 - 8月1日12:00\n"
            "【FakePool】限时寻访 活动时间：8月2日12:00 - 8月4日12:00"
        )
        pools = parse_gacha_pools(text, REF)
        self.assertEqual([p["name"] for p in pools], ["FakePool"])
        primary = pools[0]["primary"]
        self.assertEqual(list(pools[0].keys()), ["name", "primary"])
        self.assertEqual(list(primary.keys()), ["label", "start", "end", "raw"])
        self.assertEqual(primary["label"], "活动时间·寻访")
        self.assertTrue(primary["start"].startswith("2026-08-02T12:00:00"))
        self.assertTrue(primary["end"].startswith("2026-08-04T12:00:00"))
        self.assertIn("8月2日12:00", primary["raw"])

    def test_good_same_name_keeps_first_when_later_reversed(self):
        text = (
            "【FakePool】限时寻访 活动时间：8月2日12:00 - 8月4日12:00\n"
            "【FakePool】限时寻访 活动时间：8月1日16:00 - 8月1日12:00\n"
            "【FakePool】限时寻访 活动时间：8月1日12:00 - 8月1日12:00"
        )
        pools = parse_gacha_pools(text, REF)
        self.assertEqual(len(pools), 1)
        self.assertTrue(pools[0]["primary"]["start"].startswith("2026-08-02T12:00:00"))
        self.assertTrue(pools[0]["primary"]["end"].startswith("2026-08-04T12:00:00"))

    def test_short_cross_year_and_distinct_names(self):
        text = (
            "【短池】限时寻访 活动时间：8月1日12:00 - 8月1日16:00\n"
            "【跨年池】限时寻访 寻访时间：12月20日12:00 - 1月5日12:00\n"
            "【倒序池】限时寻访 活动时间：8月1日16:00 - 8月1日12:00"
        )
        pools = parse_gacha_pools(text, REF)
        self.assertEqual([p["name"] for p in pools], ["短池", "跨年池"])
        self.assertTrue(pools[0]["primary"]["start"].startswith("2026-08-01T12:00:00"))
        self.assertTrue(pools[0]["primary"]["end"].startswith("2026-08-01T16:00:00"))
        self.assertEqual(pools[1]["primary"]["label"], "寻访时间·寻访")
        self.assertTrue(pools[1]["primary"]["start"].startswith("2026-12-20T12:00:00"))
        self.assertTrue(pools[1]["primary"]["end"].startswith("2027-01-05T12:00:00"))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Test parse_ranges with various inputs."""

import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from common import parse_ranges, TZ
import fetch_bluearchive as ba


class TestParseRanges(unittest.TestCase):
    """Test parse_ranges with fixed ref time."""

    def setUp(self):
        # Fixed ref time: 2026-07-15 12:00:00 +08:00
        self.ref = datetime(2026, 7, 15, 12, 0, 0, tzinfo=TZ)

    def test_chinese_date_range(self):
        """Test Chinese date range: 07月10日 12:00 - 07月17日 03:59"""
        text = "活动时间：07月10日 12:00 - 07月17日 03:59"
        result = parse_ranges(text, self.ref)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["label"], "活动时间")
        self.assertIn("2026-07-10T12:00:00", result[0]["start"])
        self.assertIn("2026-07-17T03:59:00", result[0]["end"])

    def test_cross_year(self):
        """Test cross-year range: 12月25日 - 01月05日"""
        text = "活动时间：12月25日 - 01月05日"
        result = parse_ranges(text, self.ref)
        self.assertEqual(len(result), 1)
        # Should wrap to next year
        self.assertIn("2026-12-25", result[0]["start"])
        self.assertIn("2027-01-05", result[0]["end"])

    def test_no_match(self):
        """Test text with no date range"""
        text = "这是一个没有日期的文本"
        result = parse_ranges(text, self.ref)
        self.assertEqual(len(result), 0)

    def test_duplicate_ranges(self):
        """Test duplicate ranges are deduplicated"""
        text = "活动时间：07月10日 12:00 - 07月17日 03:59\n活动时间：07月10日 12:00 - 07月17日 03:59"
        result = parse_ranges(text, self.ref)
        self.assertEqual(len(result), 1)

    def test_invalid_date_feb30(self):
        """Invalid matches should not abort parsing."""
        text = "活动时间：02月30日 12:00 - 03月05日 04:00"
        self.assertEqual(parse_ranges(text, self.ref), [])

    def test_invalid_and_valid_ranges(self):
        good = "活动时间：07月16日 12:00 - 07月20日 04:00"
        bad = "活动时间：02月30日 12:00 - 03月05日 04:00"
        expected = parse_ranges(good, self.ref)
        for text in (bad + "\n" + good, good + "\n" + bad):
            with self.subTest(text=text):
                self.assertEqual(parse_ranges(text, self.ref), expected)

    def test_invalid_and_valid_deadlines(self):
        good = "2026年07月20日 18:00 结束"
        bad = "2026年02月30日 18:00 结束"
        self.assertEqual(
            parse_ranges(bad + "\n" + good, self.ref),
            parse_ranges(good, self.ref),
        )

    def test_invalid_time_preserves_valid_range(self):
        good = "活动时间：07月16日 12:00 - 07月20日 04:00"
        for bad in (
            "07月16日 25:00 - 07月20日 04:00",
            "07月16日 12:00 - 07月20日 04:99",
            "13月16日 - 13月20日",
        ):
            with self.subTest(bad=bad):
                self.assertEqual(
                    parse_ranges(bad + "\n" + good, self.ref),
                    parse_ranges(good, self.ref),
                )

    def test_single_point_deadline(self):
        """Test single point deadline: 2026年07月20日 18:00 结束"""
        text = "2026年07月20日 18:00 结束"
        result = parse_ranges(text, self.ref)
        self.assertEqual(len(result), 1)
        self.assertIn("2026-07-20T18:00:00", result[0]["end"])

    def test_iso_date_range(self):
        """Test ISO date range: 2026/07/16 06:00 - 2026/07/30 04:00"""
        text = "活动时间：2026/07/16 06:00 - 2026/07/30 04:00"
        result = parse_ranges(text, self.ref)
        self.assertEqual(len(result), 1)
        self.assertIn("2026-07-16T06:00:00", result[0]["start"])
        self.assertIn("2026-07-30T04:00:00", result[0]["end"])

    def test_explicit_start_year_omitted_end_is_one_range(self):
        samples = (
            ("活动时间：2025年7月10日12:00 - 7月24日03:59", "2025-07-10T12:00:00", "2025-07-24T03:59:00"),
            ("活动时间：2024年3月1日10:00 - 3月8日04:00", "2024-03-01T10:00:00", "2024-03-08T04:00:00"),
            ("活动时间：2025/07/10 12:00 - 07/24 03:59", "2025-07-10T12:00:00", "2025-07-24T03:59:00"),
        )
        for text, start, end in samples:
            with self.subTest(text=text):
                result = parse_ranges(text, self.ref)
                self.assertEqual([(r["start"][:19], r["end"][:19]) for r in result], [(start, end)])

    def test_explicit_cross_year_and_omitted_end_year(self):
        samples = (
            ("活动时间：2025年12月25日12:00 - 2026年1月5日04:00", "2025-12-25T12:00:00", "2026-01-05T04:00:00"),
            ("活动时间：2026年12月25日12:00 - 1月5日04:00", "2026-12-25T12:00:00", "2027-01-05T04:00:00"),
            ("活动时间：2025/12/25 12:00 - 2026/01/05 04:00", "2025-12-25T12:00:00", "2026-01-05T04:00:00"),
            ("活动时间：2026/12/25 12:00 - 01/05 04:00", "2026-12-25T12:00:00", "2027-01-05T04:00:00"),
        )
        for text, start, end in samples:
            with self.subTest(text=text):
                result = parse_ranges(text, self.ref)
                self.assertEqual([(r["start"][:19], r["end"][:19]) for r in result], [(start, end)])

    def test_explicit_reverse_is_skipped(self):
        for text in (
            "2026年12月25日12:00 - 2026年1月5日04:00",
            "活动时间：2026/12/25 12:00 - 2026/01/05 04:00",
            "2026年7月24日12:00 - 2025年7月10日03:59",
        ):
            with self.subTest(text=text):
                self.assertEqual(parse_ranges(text, self.ref), [])

    def test_same_line_separator_keeps_both_ranges(self):
        explicit = "活动时间：2025年7月10日12:00 - 2025年7月24日03:59"
        yearless = "开放时间：8月1日10:00 - 8月5日04:00"
        expect = {
            ("2025-07-10T12:00:00", "2025-07-24T03:59:00"),
            ("2026-08-01T10:00:00", "2026-08-05T04:00:00"),
        }
        for text in (
            explicit + "；" + yearless,
            explicit + " " + yearless,
            yearless + "；" + explicit,
            yearless + " " + explicit,
        ):
            with self.subTest(text=text):
                got = {(r["start"][:19], r["end"][:19]) for r in parse_ranges(text, self.ref)}
                self.assertEqual(got, expect)

    def test_bad_explicit_same_line_does_not_fake_yearless(self):
        bad = "活动时间：2025年2月30日12:00 - 3月5日04:00"
        good = "开放时间：8月1日10:00 - 8月5日04:00"
        expect = [("2026-08-01T10:00:00", "2026-08-05T04:00:00")]
        for text in (bad + "；" + good, bad + " " + good, good + "；" + bad, good + " " + bad):
            with self.subTest(text=text):
                result = parse_ranges(text, self.ref)
                self.assertEqual([(r["start"][:19], r["end"][:19]) for r in result], expect)

    def test_explicit_and_separate_yearless_both_kept(self):
        text = "活动时间：2025年7月10日12:00 - 7月24日03:59\n开放时间：8月1日10:00 - 8月5日04:00"
        got = {(r["start"][:19], r["end"][:19]) for r in parse_ranges(text, self.ref)}
        self.assertEqual(
            got,
            {
                ("2025-07-10T12:00:00", "2025-07-24T03:59:00"),
                ("2026-08-01T10:00:00", "2026-08-05T04:00:00"),
            },
        )

    def test_bad_explicit_does_not_fall_back_to_yearless_fragment(self):
        samples = (
            (
                "活动时间：2025年2月30日12:00 - 3月5日04:00\n活动时间：7月16日12:00 - 7月20日04:00",
                "2026-07-16T12:00:00",
            ),
            (
                "活动时间：2025年7月10日25:00 - 7月24日03:59\n开放时间：8月1日10:00 - 8月3日04:00",
                "2026-08-01T10:00:00",
            ),
            (
                "活动时间：2025/02/30 12:00 - 03/05 04:00\n活动时间：7月16日12:00 - 7月20日04:00",
                "2026-07-16T12:00:00",
            ),
        )
        for text, start in samples:
            with self.subTest(text=text):
                result = parse_ranges(text, self.ref)
                self.assertEqual([r["start"][:19] for r in result], [start])

    def test_explicit_duplicates_collapsed(self):
        for text in (
            "活动时间：2025年7月10日12:00 - 7月24日03:59\n活动时间：2025年7月10日12:00 - 7月24日03:59",
            "活动时间：2025/07/10 12:00 - 07/24 03:59\n活动时间：2025/07/10 12:00 - 07/24 03:59",
        ):
            with self.subTest(text=text):
                self.assertEqual(len(parse_ranges(text, self.ref)), 1)


class TestBlueArchiveOffline(unittest.TestCase):
    def run_rows(self, rows):
        ref = datetime(2026, 7, 15, 12, tzinfo=TZ)
        with (
            patch.object(ba, "fetch_pages", return_value=rows),
            patch.object(ba, "now_cn", return_value=ref),
            patch("common.now_cn", return_value=ref),
            patch.object(ba, "cache_cover", return_value=""),
            patch.object(ba, "http_get_json", side_effect=AssertionError("Network forbidden")),
            patch.object(ba, "write_events") as write,
        ):
            self.assertEqual(ba.main(), 0)
            write.assert_called_once()
            return write.call_args.args[1]

    def test_bad_announcement_does_not_drop_good_or_mixed(self):
        bad = "活动时间：02月30日 12:00 - 03月05日 04:00"
        good = "活动时间：07月16日 12:00 - 07月20日 04:00"
        rows = [
            {"id": 1, "title": "限时活动：坏日期", "content": bad},
            {"id": 2, "title": "限时活动：好日期", "content": good},
            {"id": 3, "title": "限时活动：混合日期", "content": bad + "\n" + good},
        ]
        payload = self.run_rows(rows)
        self.assertEqual({e["id"] for e in payload["events"]}, {"2", "3"})
        self.assertEqual(payload["count"], 2)
        for event in payload["events"]:
            self.assertEqual(event["start"], "2026-07-16T12:00:00+08:00")
            self.assertFalse(event["fuzzy"])
            self.assertEqual(event["status"], "即将开始")

    def test_bad_single_date_does_not_abort_main(self):
        payload = self.run_rows([
            {"id": 1, "title": "限时活动：坏日期", "content": "07月32日 14:00 开启"},
            {"id": 2, "title": "限时活动：好日期", "content": "07月16日 14:00 开启"},
        ])
        self.assertEqual([e["id"] for e in payload["events"]], ["2"])

    def test_old_explicit_year_not_reparsed_as_current_year(self):
        payload = self.run_rows([
            {"id": 11, "title": "限时活动：旧公告", "content": "活动时间：2025年7月10日12:00 - 7月24日03:59"},
            {"id": 12, "title": "限时活动：好公告", "content": "活动时间：2026年8月1日10:00 - 8月20日04:00"},
        ])
        self.assertEqual([e["id"] for e in payload["events"]], ["12"])
        self.assertEqual(payload["events"][0]["start"], "2026-08-01T10:00:00+08:00")

    def test_single_date_fallback_keeps_later_valid_date(self):
        payload = self.run_rows([
            {"id": 3, "title": "限时活动：混合日期",
             "content": "07月32日 14:00 开启\n07月16日 14:00 开启"},
        ])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["events"][0]["start"], "2026-07-16T14:00:00+08:00")
        self.assertTrue(payload["events"][0]["fuzzy"])


if __name__ == "__main__":
    unittest.main()

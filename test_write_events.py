#!/usr/bin/env python3
"""write_events 单文件发布。只写临时目录。"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

import common
from common import write_events


def dumped(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


OLD = {
    "game": "虚构",
    "count": 1,
    "notes": ["旧备注"],
    "events": [{"title": "旧活动", "header": "旧标题"}],
}
NEW = {
    "game": "虚构",
    "count": 1,
    "notes": ["新备注"],
    "events": [{"title": "新活动", "header": "新标题"}],
}


class WriteEventsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name) / "data"
        self.data.mkdir()
        self.path = self.data / "events.json"
        self._data = common.DATA
        self._dry = common.DRY_RUN
        common.DATA = self.data
        common.DRY_RUN = False

    def tearDown(self):
        common.DATA = self._data
        common.DRY_RUN = self._dry

    def seed(self, payload: dict) -> bytes:
        text = dumped(payload)
        self.path.write_text(text, encoding="utf-8")
        return self.path.read_bytes()

    def leftovers(self) -> list[Path]:
        return list(self.data.glob(".events-*"))

    def test_overwrite_and_create(self):
        old = self.seed(OLD)
        write_events(self.path, NEW)
        self.assertEqual(self.path.read_text(encoding="utf-8"), dumped(NEW))
        self.assertNotEqual(self.path.read_bytes(), old)
        self.assertEqual(self.leftovers(), [])

        fresh = self.data / "new.json"
        self.assertFalse(fresh.exists())
        write_events(fresh, NEW)
        self.assertEqual(fresh.read_text(encoding="utf-8"), dumped(NEW))
        self.assertEqual(self.leftovers(), [])

    def test_serialize_failure_keeps_old(self):
        old = self.seed(OLD)
        bad = {"count": 1, "events": [{"title": "坏", "blob": {1, 2}}]}
        with self.assertRaises(TypeError):
            write_events(self.path, bad)
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(self.leftovers(), [])

    def test_partial_write_keeps_old(self):
        old = self.seed(OLD)
        orig = Path.write_text

        def partial(self_path, text, encoding=None, errors=None, newline=None):
            orig(self_path, text[:8], encoding=encoding or "utf-8")
            raise OSError("partial")

        with patch.object(Path, "write_text", partial):
            with self.assertRaises(OSError):
                write_events(self.path, NEW)
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(self.leftovers(), [])

    def test_replace_failure_keeps_old(self):
        old = self.seed(OLD)
        with patch("common.os.replace", side_effect=OSError("replace")):
            with self.assertRaises(OSError):
                write_events(self.path, NEW)
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(self.leftovers(), [])

    def test_pending_empty_keeps_old_events_and_notes(self):
        self.seed(OLD)
        write_events(
            self.path,
            {
                "game": "虚构",
                "pending": True,
                "count": 0,
                "notes": ["本次没有"],
                "events": [],
            },
        )
        got = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(got["events"], OLD["events"])
        self.assertEqual(got["notes"], ["本次没有", "抓取为空，保留旧数据 1 条"])
        self.assertFalse(got["pending"])
        self.assertTrue(got["keptPrevious"])
        self.assertEqual(got["count"], 1)
        self.assertEqual(self.leftovers(), [])

    def test_dry_run_does_not_touch_target(self):
        old = self.seed(OLD)
        common.DRY_RUN = True
        write_events(self.path, NEW)
        self.assertEqual(self.path.read_bytes(), old)
        write_events(
            self.path,
            {"game": "虚构", "pending": True, "count": 0, "notes": ["空"], "events": []},
        )
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(self.leftovers(), [])


if __name__ == "__main__":
    unittest.main()

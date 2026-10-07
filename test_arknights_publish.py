#!/usr/bin/env python3
"""方舟 main 写盘。mock fetch_all，只写临时目录。"""

import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

import common
import fetch_arknights as ark
from test_write_events import dumped

OLD = {
    "game": "虚构",
    "count": 1,
    "events": [{"title": "旧活动", "header": "旧标题"}],
}
NEW = {
    "game": "虚构",
    "count": 1,
    "events": [
        {
            "title": "虚构活动",
            "status": "进行中",
            "remain": "1天",
            "start": "2026-07-01T12:00:00",
            "end": "2026-07-10T04:00:00",
            "hasSchedule": True,
        }
    ],
}


class ArknightsPublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.data = root / "data"
        self.out = root / "out"
        self.out.mkdir()
        self.path = self.out / "events.json"
        self._data = common.DATA
        self._dry = common.DRY_RUN
        self._out = ark.OUT
        common.DATA = self.data
        common.DRY_RUN = False
        ark.OUT = self.path
        self.net = patch.object(ark, "urlopen", side_effect=AssertionError("network"))
        self.cover = patch.object(common, "cache_cover", side_effect=AssertionError("cover"))
        self.net.start()
        self.cover.start()
        self.addCleanup(self.net.stop)
        self.addCleanup(self.cover.stop)

    def tearDown(self):
        common.DATA = self._data
        common.DRY_RUN = self._dry
        ark.OUT = self._out

    def seed(self, payload: dict) -> bytes:
        self.path.write_text(dumped(payload), encoding="utf-8")
        return self.path.read_bytes()

    def leftovers(self) -> list[Path]:
        return list(self.out.glob(".events-*"))

    def run_main(self, payload=NEW):
        buf = StringIO()
        with patch.object(ark, "fetch_all", return_value=payload):
            with redirect_stdout(buf):
                code = ark.main()
        return code, buf.getvalue()

    def test_dry_run_keeps_existing_and_skips_missing(self):
        old = self.seed(OLD)
        common.DRY_RUN = True
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(self.path.read_bytes(), old)
        self.assertNotIn("[ok] 写入", out)
        self.assertIn("解析到时间表", out)
        self.assertEqual(self.leftovers(), [])

        missing = self.out / "missing.json"
        ark.OUT = missing
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertFalse(missing.exists())
        self.assertNotIn("[ok] 写入", out)
        self.assertEqual(self.leftovers(), [])

    def test_write_valid_json(self):
        code, out = self.run_main()
        self.assertEqual(code, 0)
        self.assertEqual(self.path.read_text(encoding="utf-8"), dumped(NEW))
        self.assertEqual(self.leftovers(), [])
        self.assertIn("解析到时间表", out)

    def test_partial_write_keeps_old(self):
        old = self.seed(OLD)
        orig = Path.write_text

        def partial(self_path, text, encoding=None, errors=None, newline=None):
            orig(self_path, text[:8], encoding=encoding or "utf-8")
            raise OSError("partial")

        with patch.object(Path, "write_text", partial):
            with self.assertRaises(OSError):
                self.run_main()
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(self.leftovers(), [])

    def test_replace_failure_keeps_old(self):
        old = self.seed(OLD)
        with patch("common.os.replace", side_effect=OSError("replace")):
            with self.assertRaises(OSError):
                self.run_main()
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(self.leftovers(), [])

    def test_fetch_failure_does_not_write(self):
        old = self.seed(OLD)
        with patch.object(ark, "fetch_all", side_effect=RuntimeError("down")):
            with self.assertRaises(RuntimeError):
                ark.main()
        self.assertEqual(self.path.read_bytes(), old)
        self.assertEqual(self.leftovers(), [])

        missing = self.out / "missing.json"
        ark.OUT = missing
        with patch.object(ark, "fetch_all", side_effect=RuntimeError("down")):
            with self.assertRaises(RuntimeError):
                ark.main()
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()

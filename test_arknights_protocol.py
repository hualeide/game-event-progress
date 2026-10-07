#!/usr/bin/env python3
"""方舟 http_get_json / cache_cover 只允许绝对 HTTP(S)。临时文件和 127.0.0.1。"""

import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

import fetch_arknights as ark
from fetch_arknights import UA, cache_cover, http_get_json


BAD = [
    "ftp://127.0.0.1/a.jpg",
    "data:text/plain,hello",
    "covers/a.jpg",
    "/covers/a.jpg",
    "//127.0.0.1/a.jpg",
    "http://",
    "http:///tmp/x",
    "http://[",
]


class RejectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cover = Path(self.tmp.name) / "covers"
        self._cover = ark.COVER_DIR
        ark.COVER_DIR = self.cover
        self.secret = Path(self.tmp.name) / "generated.txt"
        self.secret.write_bytes(b"n" * 13200)
        self.file_url = self.secret.resolve().as_uri()

    def tearDown(self):
        ark.COVER_DIR = self._cover

    def test_file_url_not_copied(self):
        self.assertEqual(cache_cover("generated", self.file_url), "")
        self.assertFalse((self.cover / "generated.jpg").exists())
        self.assertFalse(self.cover.exists())
        self.assertEqual(self.secret.read_bytes(), b"n" * 13200)
        with self.assertRaises(URLError):
            http_get_json(self.file_url)
        self.assertEqual(self.secret.read_bytes(), b"n" * 13200)

    def test_preset_illegal_cache_not_linked(self):
        self.cover.mkdir()
        (self.cover / "generated.jpg").write_bytes(b"Q" * 2000)
        self.assertEqual(cache_cover("generated", self.file_url), "")

    def test_bad_urls_rejected_before_open(self):
        opened = []

        def track(req, timeout=None):
            opened.append(getattr(req, "full_url", str(req)))
            raise AssertionError("opened")

        targets = [self.file_url, *BAD]
        with patch.object(ark, "urlopen", track):
            for url in targets:
                with self.subTest(url=url):
                    with self.assertRaises(URLError):
                        http_get_json(url)
                    self.assertEqual(cache_cover("generated", url), "")
                    self.assertFalse((self.cover / "generated.jpg").exists())
        self.assertEqual(opened, [])


class LocalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file_url = ""
        cls.ftp_port = 0
        cls.seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                LocalTests.seen.append(
                    {
                        "path": self.path,
                        "ua": self.headers.get("User-Agent"),
                        "accept": self.headers.get("Accept"),
                        "referer": self.headers.get("Referer"),
                    }
                )
                if self.path == "/notice":
                    self._send(200, b'{"n":1}', "application/json")
                elif self.path == "/poster.jpg":
                    self._send(200, b"P" * 600, "image/jpeg")
                elif self.path == "/tiny.jpg":
                    self._send(200, b"t" * 100, "image/jpeg")
                elif self.path == "/missing.jpg":
                    self._send(404, b"", "text/plain")
                elif self.path == "/to-poster":
                    self._redirect(302, "/poster.jpg")
                elif self.path == "/to-notice":
                    self._redirect(302, "/notice")
                elif self.path == "/to-file":
                    self._redirect(302, LocalTests.file_url)
                elif self.path == "/to-ftp":
                    self._redirect(301, f"ftp://127.0.0.1:{LocalTests.ftp_port}/a.jpg")
                else:
                    self._send(404, b"", "text/plain")

            def _send(self, code, body: bytes, ctype: str):
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Type", ctype)
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def _redirect(self, code, location: str):
                self.send_response(code)
                self.send_header("Location", location)
                self.end_headers()

            def log_message(self, fmt, *args):
                return

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.port}"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cover = Path(self.tmp.name) / "covers"
        self._cover = ark.COVER_DIR
        ark.COVER_DIR = self.cover
        note = Path(self.tmp.name) / "generated.txt"
        note.write_bytes(b"n" * 13200)
        type(self).file_url = note.resolve().as_uri()
        type(self).seen = []

    def tearDown(self):
        ark.COVER_DIR = self._cover

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_http_download_headers_timeout_and_cache(self):
        seen = {}
        real_open = ark.urlopen
        real_get = getattr(ark, "http_get", None)

        def spy_open(req, timeout=None):
            seen["timeout"] = timeout
            return real_open(req, timeout=timeout)

        def spy_get(url, headers=None, timeout=40):
            seen["timeout"] = timeout
            return real_get(url, headers, timeout)

        patches = [patch.object(ark, "urlopen", spy_open)]
        if real_get is not None:
            patches.append(patch.object(ark, "http_get", spy_get))
        with patches[0] if len(patches) == 1 else _stack(patches):
            data = http_get_json(f"{self.base}/notice")
        self.assertEqual(data, {"n": 1})
        self.assertEqual(seen["timeout"], 30)
        hit = self.seen[-1]
        self.assertEqual(hit["ua"], UA)
        self.assertEqual(hit["accept"], "application/json")

        seen.clear()
        type(self).seen = []
        with patches[0] if len(patches) == 1 else _stack(patches):
            link = cache_cover("poster", f"{self.base}/poster.jpg")
        self.assertEqual(link, "./covers/poster.jpg")
        self.assertEqual((self.cover / "poster.jpg").read_bytes(), b"P" * 600)
        self.assertEqual(seen["timeout"], 40)
        img = self.seen[-1]
        self.assertEqual(img["path"], "/poster.jpg")
        self.assertEqual(img["ua"], UA)
        self.assertEqual(img["accept"], "image/*,*/*")
        self.assertEqual(img["referer"], "https://ak.hypergryph.com/")

        self.assertEqual(cache_cover("tiny", f"{self.base}/tiny.jpg"), f"{self.base}/tiny.jpg")
        self.assertFalse((self.cover / "tiny.jpg").exists())
        self.assertEqual(cache_cover("gone", f"{self.base}/missing.jpg"), f"{self.base}/missing.jpg")

        https = "https://cdn.example.test/hero.png"
        preset = self.cover / "hero.png"
        preset.write_bytes(b"C" * 1001)

        def boom(*args, **kwargs):
            raise AssertionError("cache hit must not download")

        guards = [patch.object(ark, "urlopen", boom)]
        if hasattr(ark, "http_get"):
            guards.append(patch.object(ark, "http_get", boom))
        with _stack(guards):
            self.assertEqual(cache_cover("hero", https), "./covers/hero.png")

    def test_http_redirect_kept_file_and_ftp_rejected(self):
        link = cache_cover("poster", f"{self.base}/to-poster")
        self.assertEqual(link, "./covers/poster.jpg")
        self.assertEqual((self.cover / "poster.jpg").read_bytes(), b"P" * 600)
        self.assertEqual(http_get_json(f"{self.base}/to-notice"), {"n": 1})

        before = cache_cover("poster", f"{self.base}/to-file")
        self.assertEqual(before, f"{self.base}/to-file")
        self.assertFalse(any(p.read_bytes() == b"n" * 13200 for p in self.cover.glob("*")))
        with self.assertRaises(URLError):
            http_get_json(f"{self.base}/to-file")

        hit = {"ok": False}
        sock = __import__("socket").socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        sock.settimeout(0.5)
        type(self).ftp_port = sock.getsockname()[1]

        def watch():
            try:
                conn, _ = sock.accept()
                hit["ok"] = True
                try:
                    conn.sendall(b"220 nope\r\n")
                finally:
                    conn.close()
            except OSError:
                pass

        threading.Thread(target=watch, daemon=True).start()
        try:
            self.assertEqual(cache_cover("poster", f"{self.base}/to-ftp"), f"{self.base}/to-ftp")
            self.assertFalse(hit["ok"])
        finally:
            sock.close()


def _stack(patches):
    from contextlib import ExitStack

    stack = ExitStack()
    for item in patches:
        stack.enter_context(item)
    return stack


if __name__ == "__main__":
    unittest.main()

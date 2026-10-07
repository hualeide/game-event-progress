#!/usr/bin/env python3
"""封面/下载只允许绝对 HTTP(S)。只用临时文件和 127.0.0.1。"""

import hashlib
import sys
import tempfile
import threading
import unittest
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

import common
from common import cache_cover, http_get, safe_stem


def cover_name(cid: str, url: str) -> str:
    low = url.lower().split("?")[0]
    ext = ".jpg"
    if low.endswith(".png"):
        ext = ".png"
    elif low.endswith(".webp"):
        ext = ".webp"
    elif low.endswith(".jpeg"):
        ext = ".jpg"
    fp = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    return f"{safe_stem(cid)}-{fp}{ext}"


class Resp:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._data


class CoverProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cover = Path(self.tmp.name) / "covers"
        self._cover = common.COVER_DIR
        common.COVER_DIR = self.cover
        blob = b"n" * 11200
        self.secret = Path(self.tmp.name) / "note.txt"
        self.secret.write_bytes(blob)
        self.file_url = self.secret.resolve().as_uri()

    def tearDown(self):
        common.COVER_DIR = self._cover

    def test_file_url_not_published(self):
        self.assertEqual(cache_cover("cid", self.file_url), "")
        self.assertFalse(self.cover.exists())
        self.assertEqual(self.secret.read_bytes(), b"n" * 11200)

    def test_preset_illegal_cache_not_linked(self):
        self.cover.mkdir()
        name = cover_name("cid", self.file_url)
        (self.cover / name).write_bytes(b"Q" * 9000)
        self.assertEqual(cache_cover("cid", self.file_url), "")

    def test_rejected_urls_do_not_open(self):
        opened = []

        def track(req, timeout=None):
            opened.append(getattr(req, "full_url", req))
            raise AssertionError("opened")

        class Opener:
            def open(self, req, timeout=None):
                return track(req, timeout)

        urls = [
            self.file_url,
            "ftp://example.test/a.jpg",
            "data:text/plain,hello",
            "covers/a.jpg",
            "/covers/a.jpg",
            "//cdn.example.test/a.jpg",
            "http://",
            "http:///tmp/x",
            "http://[",
        ]
        patches = []
        if hasattr(common, "urlopen"):
            patches.append(patch("common.urlopen", track))
        if hasattr(common, "build_opener"):
            patches.append(patch("common.build_opener", return_value=Opener()))
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            for url in urls:
                with self.subTest(url=url):
                    with self.assertRaises(URLError):
                        http_get(url)
                    self.assertEqual(cache_cover("c", url), "")
        self.assertEqual(opened, [])
        self.assertFalse(self.cover.exists())


class LocalHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ftp_hit = False
        cls.ftp = __import__("socket").socket()
        cls.ftp.bind(("127.0.0.1", 0))
        cls.ftp.listen(1)
        cls.ftp.settimeout(0.3)
        cls.ftp_port = cls.ftp.getsockname()[1]
        cls.file_url = ""

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in ("/big", "/big.jpg", "/big.png"):
                    body = b"I" * 9000
                    self._send(200, body)
                elif self.path in ("/small", "/small.jpg", "/small.png"):
                    self._send(200, b"s" * 100)
                elif self.path == "/hang":
                    import time
                    time.sleep(2)
                    self._send(200, b"I" * 9000)
                elif self.path == "/to-big":
                    self.send_response(302)
                    self.send_header("Location", "/big")
                    self.end_headers()
                elif self.path == "/to-file":
                    self.send_response(302)
                    self.send_header("Location", cls.file_url)
                    self.end_headers()
                elif self.path == "/to-ftp":
                    self.send_response(301)
                    self.send_header("Location", f"ftp://127.0.0.1:{cls.ftp_port}/a.jpg")
                    self.end_headers()
                else:
                    self._send(404, b"")

            def _send(self, code, body: bytes):
                self.send_response(code)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Type", "image/jpeg")
                self.end_headers()
                if body:
                    self.wfile.write(body)

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
        self._cover = common.COVER_DIR
        common.COVER_DIR = self.cover
        note = Path(self.tmp.name) / "note.txt"
        note.write_bytes(b"n" * 11200)
        type(self).file_url = note.resolve().as_uri()

    def tearDown(self):
        common.COVER_DIR = self._cover

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.ftp.close()

    def test_http_download_short_and_cache_hit(self):
        link = cache_cover("big", f"{self.base}/big.jpg")
        self.assertTrue(link.startswith("./covers/"))
        saved = self.cover / link.split("/")[-1]
        self.assertEqual(saved.read_bytes(), b"I" * 9000)

        self.assertEqual(cache_cover("small", f"{self.base}/small.jpg"), "")
        self.assertFalse((self.cover / cover_name("small", f"{self.base}/small.jpg")).exists())

        https = "https://cdn.example.test/hero.png"
        preset = self.cover / cover_name("hit", https)
        preset.write_bytes(b"C" * 9000)

        def boom(*args, **kwargs):
            raise AssertionError("cache hit must not download")

        with patch("common.http_get", boom):
            self.assertEqual(cache_cover("hit", https), f"./covers/{preset.name}")

        seen = {}
        real = common.http_get

        def spy(url, headers=None, timeout=40):
            seen["timeout"] = timeout
            return real(url, headers, timeout=timeout)

        with patch("common.http_get", spy):
            self.assertTrue(cache_cover("big2", f"{self.base}/big.png").startswith("./covers/"))
        self.assertEqual(seen["timeout"], 15)

        with self.assertRaises(Exception):
            http_get(f"{self.base}/hang", timeout=0.3)

    def test_redirect_stays_on_http(self):
        data = http_get(f"{self.base}/to-big")
        self.assertEqual(data, b"I" * 9000)

        with self.assertRaises(URLError):
            http_get(f"{self.base}/to-file")
        self.assertFalse(any(p.suffix == ".jpg" and p.read_bytes() == b"n" * 11200 for p in self.cover.glob("*")))

        with self.assertRaises(URLError):
            http_get(f"{self.base}/to-ftp", timeout=0.5)
        hit = False
        try:
            conn, _ = self.ftp.accept()
            hit = True
            conn.close()
        except OSError:
            hit = False
        self.assertFalse(hit)


if __name__ == "__main__":
    unittest.main()

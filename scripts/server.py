#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静态站 + 简易运维 API（Docker / VPS 用）。

  GET  /api/health          健康检查 + 最近更新时间
  POST /api/trigger-update  手动触发抓取（60 秒冷却）
  GET  /api/update-log      最近一次更新日志

静态文件根目录：public/
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT = Path(__file__).resolve().parent.parent
PUBLIC = PROJECT / "public"
DATA = PROJECT / "data"
LOG_FILE = DATA / "update-server.log"
COOLDOWN_SEC = 60

_lock = threading.Lock()
_last_trigger = 0.0
_updating = False


def _read_status() -> dict:
    for path in (PUBLIC / "data" / "status.json", DATA / "status.json"):
        try:
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def _run_update() -> int:
    global _updating
    DATA.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(PROJECT / "scripts" / "update.py"), "--jobs", "1", "--timeout", "300"]
    with LOG_FILE.open("w", encoding="utf-8") as log:
        log.write(f"$ {' '.join(cmd)}\n")
        log.flush()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(PROJECT),
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            log.write(f"\n[exit {proc.returncode}]\n")
            return proc.returncode
        except Exception as exc:  # noqa: BLE001
            log.write(f"\n[error] {exc}\n")
            return 1
        finally:
            with _lock:
                _updating = False


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _text(self, code: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            st = _read_status()
            self._json(
                200,
                {
                    "ok": True,
                    "updatedAt": st.get("updatedAt"),
                    "fetchOk": st.get("fetchOk"),
                    "message": st.get("message"),
                    "updating": _updating,
                },
            )
            return
        if path == "/api/update-log":
            if not LOG_FILE.is_file():
                self._text(404, "暂无更新日志")
                return
            self._text(200, LOG_FILE.read_text(encoding="utf-8", errors="replace"))
            return
        if path in ("/", ""):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/trigger-update":
            self._json(404, {"ok": False, "error": "not found"})
            return

        global _last_trigger, _updating
        now = time.time()
        with _lock:
            if _updating:
                err = ("busy", None)
            else:
                waited = now - _last_trigger
                if _last_trigger and waited < COOLDOWN_SEC:
                    err = ("cooldown", int(COOLDOWN_SEC - waited) + 1)
                else:
                    _last_trigger = now
                    _updating = True
                    err = None

        if err and err[0] == "busy":
            self._json(409, {"ok": False, "error": "update already running"})
            return
        if err and err[0] == "cooldown":
            self._json(429, {"ok": False, "error": "cooldown", "retryAfterSec": err[1]})
            return

        threading.Thread(target=_run_update, name="trigger-update", daemon=True).start()
        self._json(202, {"ok": True, "message": "update started"})


def main() -> int:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))
    if not PUBLIC.is_dir():
        print(f"[server] missing public/: {PUBLIC}", file=sys.stderr)
        return 1
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"[server] http://{host}:{port}/  (root={PUBLIC})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] stopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

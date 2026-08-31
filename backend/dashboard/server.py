"""HTTP presentation server for Commercial Intelligence Dashboard V1."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from backend.dashboard.jsonutil import json_safe
from backend.dashboard.loader import DashboardStore, load_store
from backend.dashboard.query import assemble, opportunity_detail

STATIC_DIR = Path(__file__).resolve().parent / "static"


class DashboardHandler(SimpleHTTPRequestHandler):
    store: DashboardStore

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/api/health":
            self._send_json(
                {"status": "ok", "manufacturer": self.store.manufacturer, "period": self.store.current_period}
            )
            return
        if parsed.path == "/api/dashboard":
            params = {key: values[-1] if values else None for key, values in parse_qs(parsed.query).items()}
            payload = assemble(
                self.store,
                period=params.get("period"),
                category=params.get("category"),
                brand=params.get("brand"),
                product=params.get("product"),
                retailer=params.get("retailer"),
                region=params.get("region"),
                lever=params.get("lever"),
                top_n=int(params.get("top_n") or 3),
            )
            self._send_json(payload)
            return
        if parsed.path == "/api/opportunity":
            params = parse_qs(parsed.query)
            opportunity_id = (params.get("id") or [None])[0]
            if not opportunity_id:
                self._send_json({"error": "id is required"}, status=400)
                return
            payload = opportunity_detail(self.store, opportunity_id)
            if payload is None:
                self._send_json({"error": "Opportunity not found"}, status=404)
                return
            self._send_json(payload)
            return
        super().do_GET()

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.is_file():
            self.send_error(404, "Not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(json_safe(payload), ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Commercial Intelligence Dashboard V1: explore frozen Commercial Brain, storytelling, "
            "and POS facts. Does not rescore specialist agents."
        )
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default 8765)")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Data root containing brain_reports/ (default backend/data)",
    )
    return parser


def serve(host: str, port: int, data_root: Path | None = None) -> None:
    store = load_store(data_root)
    DashboardHandler.store = store
    httpd = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Commercial Intelligence Dashboard V1 → http://{host}:{port}")
    print(f"Manufacturer {store.manufacturer} | current period {store.current_period} | {store.pos_weeks} POS weeks")
    httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    serve(args.host, args.port, args.data_root)
    return 0

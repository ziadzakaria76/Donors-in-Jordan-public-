"""Serves the fixtures over HTTP on 127.0.0.1 with correct content types.

Exists because the adapters must be exercised through the real Fetcher --
headers, content-type sniffing, status handling and the delay floor included.
Importing the parse functions directly would test less than it appears to.

This is NOT a substitute for calling a real endpoint. It proves the parsing,
not the endpoint.
"""

from __future__ import annotations

import http.server
import threading
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"

ROUTES = {
    "/sf/search": ("successfactors_search.json", "application/json", 200),
    "/orc/requisitions": ("oracle_orc_requisitions.json", "application/json", 200),
    "/elevatus/api/job-posts": ("elevatus_job_posts.json", "application/json", 200),
    "/careers": ("careers_table.html", "text/html; charset=utf-8", 200),
    # Failure shapes the adapters must report rather than swallow.
    "/empty": (None, "application/json", 200),
    "/forbidden": (None, "application/json", 403),
    "/notjson": (None, "application/json", 200),
}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):   # keep test output clean
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path not in ROUTES:
            self.send_error(404)
            return
        name, content_type, status = ROUTES[path]
        if path == "/empty":
            body = b'{"jobs": []}'
        elif path == "/forbidden":
            body = b'{"error": "Access denied for this site number"}'
        elif path == "/notjson":
            body = b"<html><body>Sign in to continue</body></html>"
        else:
            body = (FIXTURES / name).read_bytes()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_POST = do_GET


def start(port: int = 8731):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"

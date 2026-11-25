"""Local HTTP service and review API. Run with python -m invoice_review.server."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
from threading import BoundedSemaphore
from urllib.parse import parse_qs, unquote, urlsplit

from PIL import Image

from .documents import MAX_BYTES
from .export import export
from .extract import MODELS
from .pipeline import ingest
from .review import display
from .store import Conflict, Store

STATIC = Path(__file__).with_name("static")
POLICY = Path(__file__).resolve().parents[1] / "results" / "policy.json"
RECORD = re.compile(r"/api/invoices/([0-9a-f]{32})(?:/(export|page)/(json|csv|[1-8]))?")
ASSETS = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/style.css": ("style.css", "text/css")}


def handler(store, policy):
    queue = BoundedSemaphore(2)

    class Handler(BaseHTTPRequestHandler):
        def send(self, status, body, mime, name=None):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            if name:
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.end_headers()
            self.wfile.write(body)

        def json(self, data, status=200):
            self.send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def body(self, limit):
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= limit:
                raise ValueError("Request is empty or exceeds the size limit.")
            return self.rfile.read(size)

        def dispatch(self, write):
            url = urlsplit(self.path)
            host = self.headers.get("Host", "")
            if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                return self.json({"error": "Use the loopback application URL."}, 403)
            if write:
                # Only local UI requests with a matching Origin can mutate state.
                if self.headers.get("Origin") != f"http://{self.headers.get('Host')}":
                    return self.json({"error": "Open the local application to submit changes."}, 403)
                if url.path == "/api/invoices":
                    options = parse_qs(url.query)
                    method = options.get("method", ["layout"])[0]
                    enhance = options.get("enhance", ["0"])[0] == "1"
                    if method not in MODELS:
                        raise ValueError("Unknown extraction method.")
                    filename = unquote(self.headers.get("X-Invoice-Filename", ""))[:250]
                    if not queue.acquire(blocking=False):
                        return self.json({"error": "Two invoices are already processing. Try again shortly."}, 429)
                    try:
                        identifier, record = ingest(store, filename, self.body(MAX_BYTES), method, policy,
                                                    enhance=enhance)
                    finally:
                        queue.release()
                    return self.json({"id": identifier, **display(record)}, 201)
            if not write and url.path in ASSETS:
                file, mime = ASSETS[url.path]
                return self.send(200, (STATIC / file).read_bytes(), mime + "; charset=utf-8")
            match = RECORD.fullmatch(url.path)
            if not match:
                raise KeyError("Page not found.")
            identifier, operation, value = match.groups()
            if write:
                if operation is not None:
                    raise KeyError("Action not found.")
                action = json.loads(self.body(16_384))
                if not isinstance(action, dict):
                    raise ValueError("Expected a review action.")
                record = store.apply(identifier, action.get("revision"), action)
                return self.json({"id": identifier, **display(record)})
            record = store.get(identifier)
            if operation == "page" and value.isdecimal():
                path = store.root / identifier / f"page-{value}.png"
                if not path.is_file():
                    raise KeyError("Page not found.")
                return self.send(200, path.read_bytes(), "image/png")
            if operation == "export" and value in ("json", "csv"):
                mime = "application/json" if value == "json" else "text/csv"
                return self.send(200, export(record, value).encode(), mime, f"invoice-{identifier[:8]}.{value}")
            if operation is None:
                return self.json({"id": identifier, **display(record)})
            raise KeyError("Page not found.")

        def execute(self, write):
            try:
                self.dispatch(write)
            except Conflict as error:
                self.json({"error": str(error)}, 409)
            except KeyError:
                self.json({"error": "Invoice or page not found."}, 404)
            except (ValueError, Image.UnidentifiedImageError, Image.DecompressionBombError) as error:
                self.json({"error": str(error)}, 422)
            except (RuntimeError, FileNotFoundError, subprocess.SubprocessError):
                self.json({"error": "Document processing failed. Check the local OCR and PDF tools."}, 422)

        def do_GET(self):
            self.execute(False)

        def do_POST(self):
            self.execute(True)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data", type=Path, default=Path("var"))
    parser.add_argument("--demo-policy", action="store_true",
                        help="Enable the measured synthetic automation policy for fictional demo files only")
    args = parser.parse_args()
    policy = json.loads(POLICY.read_text()) if args.demo_policy else None
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler(Store(args.data), policy)) as server:
        print(f"Invoice review at http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()

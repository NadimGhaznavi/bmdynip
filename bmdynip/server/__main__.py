"""Run the BMDynIP UI preview without DNS or updater integration."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bmdynip.constants.DBMDynIP import DBMDynIP


SERVER_DIR = Path(__file__).resolve().parent
ASSETS = {
    "/": (SERVER_DIR / "static/index.html", "text/html; charset=utf-8"),
    "/static/style.css": (SERVER_DIR / "static/style.css", "text/css; charset=utf-8"),
    "/static/ui.js": (SERVER_DIR / "static/ui.js", "text/javascript; charset=utf-8"),
    "/static/demo.js": (SERVER_DIR / "static/demo.js", "text/javascript; charset=utf-8"),
    "/pages/images/bmdynip-logo.png": (
        SERVER_DIR.parents[1] / "pages/images/bmdynip-logo.png", "image/png"),
}


class PreviewHandler(BaseHTTPRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(DBMDynIP.WEB_REQUEST_TIMEOUT)

    def do_GET(self) -> None:
        self.serve()

    def do_HEAD(self) -> None:
        self.serve()

    def serve(self) -> None:
        asset = ASSETS.get(self.path.split("?", 1)[0])
        if asset is None:
            status, body, content_type = 404, b"Not found.\n", "text/plain; charset=utf-8"
        else:
            path, content_type = asset
            body = path.read_bytes()
            if path.name == "index.html":
                body = body.replace(b"{{ version }}", DBMDynIP.VERSION.encode("ascii"))
            status = 200
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DBMDynIP.WEB_HOST)
    parser.add_argument("--port", type=int, default=DBMDynIP.WEB_PORT)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535.")
    with ThreadingHTTPServer((args.host, args.port), PreviewHandler) as server:
        print(f"BMDynIP UI preview: http://{args.host}:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

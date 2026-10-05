"""Serve BMDynIP controls backed by MariaDB."""

import argparse
from contextlib import closing
import json
import logging
import re
from urllib.parse import urlsplit

from pymysql import MySQLError, IntegrityError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path

from bmdynip.constants.DBMDynIP import DBMDynIP
from bmdynip.app.database import open_database
from bmdynip.interface.Configuration import Configuration
from bmdynip.interface.DnsRecordDb import DnsRecordDb
from bmdynip.interface.IpState import IpState
from bmdynip.interface.UiDb import UiDb
from bmdynip.interface.RunnerSchedule import RunnerSchedule
from bmdynip.interface.RunnerProcess import RunnerProcess


SERVER_DIR = files("bmdynip.server")
LOGO = SERVER_DIR / "static/bmdynip-logo.png"
if not LOGO.is_file():
    LOGO = Path(__file__).resolve().parents[2] / "pages/images/bmdynip-logo.png"
ASSETS = {
    "/": (SERVER_DIR / "static/index.html", "text/html; charset=utf-8"),
    "/static/style.css": (SERVER_DIR / "static/style.css", "text/css; charset=utf-8"),
    "/static/ui.js": (SERVER_DIR / "static/ui.js", "text/javascript; charset=utf-8"),
    "/static/api.js": (SERVER_DIR / "static/api.js", "text/javascript; charset=utf-8"),
    "/static/schedule.js": (SERVER_DIR / "static/schedule.js", "text/javascript; charset=utf-8"),
    "/pages/images/bmdynip-logo.png": (
        LOGO, "image/png"),
}


class ControlHandler(BaseHTTPRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(DBMDynIP.WEB_REQUEST_TIMEOUT)

    def do_GET(self) -> None:
        if self.path == '/api/runner-schedule':
            self.schedule()
        elif self.path == '/api/snapshot':
            self.api('snapshot')
        elif self.path == DBMDynIP.WEB_READY_PATH:
            self.api('ready')
        else:
            self.serve()

    def do_HEAD(self) -> None:
        if self.path == DBMDynIP.WEB_READY_PATH:
            self.api('ready')
        else:
            self.serve()

    def do_POST(self) -> None:
        if self.path == '/api/runner-schedule':
            self.schedule(mutating=True)
            return
        if self.path != '/api/records':
            self.respond(404, {'error': 'Not found.'})
            return
        self.api('add')

    def do_DELETE(self) -> None:
        match = re.fullmatch(r'/api/records/([1-9][0-9]*)', self.path)
        if match is None:
            self.respond(404, {'error': 'Not found.'})
            return
        self.api('remove', int(match[1]))

    def respond(self, status, value):
        body = json.dumps(value).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def allow_write(self):
        # JSON-only, same-origin writes prevent cross-site browser submissions.
        origin = self.headers.get('Origin')
        if ((origin and urlsplit(origin).netloc != self.headers.get('Host'))
                or self.headers.get('Sec-Fetch-Site') == 'cross-site'):
            self.respond(403, {'error': 'Cross-origin writes are not allowed.'})
            return False
        if self.headers.get('Content-Type') != 'application/json':
            self.respond(415, {'error': 'Use application/json.'})
            return False
        return True

    def schedule(self, mutating=False):
        if mutating and not self.allow_write():
            return
        try:
            if mutating:
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 1024:
                    raise ValueError('Invalid request size.')
                values = json.loads(self.rfile.read(length))
                if not isinstance(values, dict) or set(values) != {'enabled', 'expression'}:
                    raise ValueError('Provide an enabled flag and a five-field cron expression.')
                values = self.server.runner_schedule.update(**values)
            else:
                values = self.server.runner_schedule.read()
            self.respond(200, {'schedule': values})
        except (ValueError, UnicodeError) as error:
            self.respond(400 if mutating else 503, {'error': str(error)})
        except OSError:
            logging.exception('Could not access the runner cron entry')
            self.respond(503, {'error': 'Could not access the runner cron entry. Check the service log and retry.'})

    def api(self, operation, identity=None):
        if operation in ('add', 'remove') and not self.allow_write():
            return
        try:
            name = None
            if operation == 'add':
                length = int(self.headers.get('Content-Length', '0'))
                if not 1 <= length <= 1024:
                    raise ValueError('Invalid request size.')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or set(data) != {'name'} or not isinstance(data['name'], str):
                    raise ValueError('Supply a hostname string.')
                name = data['name']
            db = self.server.db_factory()
            try:
                if operation in ('ready', 'snapshot'):
                    snapshot = UiDb(db).snapshot(self.server.domain)
                    value, status = ({'ready': True} if operation == 'ready' else snapshot), 200
                else:
                    with IpState(self.server.state_directory).lock() as acquired:
                        if not acquired:
                            self.respond(409, {'error': 'The updater is running. Try again shortly.'})
                            return
                        with db.transaction():
                            records = DnsRecordDb(db)
                            if operation == 'add':
                                value, status = {'id': records.add(self.server.domain, name)}, 201
                            else:
                                removed = records.remove(identity)
                                value, status = ({'removed': True}, 200) if removed else ({'error': 'Record not found.'}, 404)
            finally:
                db.close()
            if operation == 'add':
                try:
                    self.server.start_runner()
                    value['runnerStarted'] = True
                except OSError:
                    logging.exception('Hostname saved but the immediate runner could not start')
                    value['runnerStarted'] = False
            self.respond(status, value)
        except IntegrityError as error:
            if error.args[0] == 1062:
                self.respond(409, {'error': 'That hostname already exists.'})
            else:
                self.respond(503, {'error': 'Database operation failed.'})
        except MySQLError:
            self.respond(503, {'error': 'Database unavailable.'})
        except (ValueError, UnicodeError):
            if operation in ('ready', 'snapshot'):
                self.respond(503, {'error': 'Server configuration unavailable.'})
            else:
                self.respond(400, {'error': 'Invalid hostname or request.'})
        except OSError:
            self.respond(503, {'error': 'Server configuration unavailable.'})

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
    with closing(RunnerProcess()) as runner, ThreadingHTTPServer((args.host, args.port), ControlHandler) as server:
        server.db_factory = open_database
        server.domain = Configuration.domain(Path(DBMDynIP.INSTALL_DIR) / 'conf/bmdynip.json')
        server.state_directory = Path(DBMDynIP.INSTALL_DIR) / 'data'
        server.runner_schedule = RunnerSchedule()
        server.start_runner = runner.start
        print(f"BMDynIP Web UI: http://{args.host}:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

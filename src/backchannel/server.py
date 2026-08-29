from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import parse_qs, urlsplit

PAGE_TEMPLATE = Path(__file__).with_name("web") / "page.html"
SAFE_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._ -]{0,126}[A-Za-z0-9])?$")
UPLOAD_CHUNK_BYTES = 64 * 1024
UPLOAD_DEADLINE_SECONDS = 5 * 60
REQUEST_TIMEOUT_SECONDS = 30
# A wrong token is answered like a wrong path, after a pause. The delay is not a
# real defence against a distributed guesser, it just makes a naive loop useless
# against a 144-bit token.
AUTH_DELAY_SECONDS = 0.25
MISSING_TRANSCRIPT = "(the mirror has not written a transcript yet)\n"


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler, config, token):
        super().__init__(address, handler)
        self.config = config
        self.token = token


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "backchannel"
    sys_version = ""
    # A client that opens a connection and then stalls holds a thread until this
    # fires. It also bounds an upload whose body never arrives in full.
    timeout = REQUEST_TIMEOUT_SECONDS

    def do_GET(self):
        route, query = self._route()
        if not self._authorized(query):
            return
        if route == "/":
            self._send(200, self._page(), "text/html")
        elif route == "/transcript.txt":
            self._send(200, self._transcript(), "text/plain")
        else:
            self._not_found()

    def do_POST(self):
        route, query = self._route()
        if not self._authorized(query):
            return
        if route == "/send":
            self._receive(query)
        else:
            self._not_found()

    def _route(self):
        parts = urlsplit(self.path)
        return parts.path.rstrip("/") or "/", parse_qs(parts.query)

    def _authorized(self, query):
        offered = (query.get("k") or [""])[0]
        if secrets.compare_digest(offered, self.server.token):
            return True
        time.sleep(AUTH_DELAY_SECONDS)
        self._not_found()
        return False

    def _page(self):
        config = self.server.config
        template = PAGE_TEMPLATE.read_text(encoding="utf-8")
        return (
            template.replace("__TITLE__", escape(config.title, quote=False))
            .replace("__YOU_JSON__", json.dumps(config.you_label))
            .replace("__AGENT_JSON__", json.dumps(config.agent_label))
        )

    def _transcript(self):
        try:
            return self.server.config.transcript_file.read_text(encoding="utf-8")
        except OSError:
            return MISSING_TRANSCRIPT

    def _receive(self, query):
        config = self.server.config
        name = (query.get("name") or [""])[0]
        if not SAFE_NAME.fullmatch(name):
            self._error(400, "invalid file name")
            return
        try:
            declared = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._error(411, "Content-Length required")
            return
        if declared > config.max_upload_bytes:
            self._error(413, "body over the limit")
            return
        if declared < 1:
            self._error(400, "empty body")
            return

        inbox = config.inbox
        inbox.mkdir(parents=True, exist_ok=True)
        if sum(1 for _ in inbox.iterdir()) >= config.max_pending_uploads:
            self._error(429, "too many pending files")
            return

        temporary = inbox / f".upload-{secrets.token_hex(8)}"
        try:
            written = self._drain(declared, temporary)
        except (TimeoutError, OSError) as error:
            temporary.unlink(missing_ok=True)
            if isinstance(error, TimeoutError):
                self._error(408, "upload did not finish in time")
            else:
                self._error(500, f"could not store the file: {error.strerror}")
            return

        os.replace(temporary, inbox / name)
        self._send(200, f"received: {name} ({written} bytes)\n", "text/plain")

    def _drain(self, declared, target):
        deadline = time.monotonic() + UPLOAD_DEADLINE_SECONDS
        written = 0
        handle = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(handle, "wb") as sink:
            while written < declared:
                if time.monotonic() > deadline:
                    raise TimeoutError
                chunk = self.rfile.read(min(UPLOAD_CHUNK_BYTES, declared - written))
                if not chunk:
                    raise TimeoutError
                sink.write(chunk)
                written += len(chunk)
        return written

    def _send(self, status, body, content_type):
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self._common_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(encoded)

    def _common_headers(self):
        # The token travels in the query string, so keep this page out of
        # caches and stop it from leaking the URL through a Referer header.
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; "
            "script-src 'unsafe-inline'; connect-src 'self'",
        )

    def _error(self, status, message):
        self._send(status, f"{message}\n", "text/plain")

    def _not_found(self):
        self._error(404, "not found")

    def log_message(self, *args):
        pass


def load_token(path):
    path = Path(path).expanduser()
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(18)
    path.write_text(token + "\n", encoding="utf-8")
    path.chmod(0o600)
    return token


def build_server(config, token=None, port=None):
    token = token or load_token(config.token_file)
    address = (config.host, config.port if port is None else port)
    return BridgeServer(address, BridgeHandler, config, token)


def run(config):
    server = build_server(config)
    server.serve_forever()
    return 0

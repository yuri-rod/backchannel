from http.client import HTTPConnection
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from backchannel import server
from backchannel.config import Config

TOKEN = "test-token"


class ServerCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = Config(
            share_root=self.root,
            token_file=self.root / "token",
            title="Night Shift",
            you_label="ME",
            agent_label="BOT",
            max_pending_uploads=3,
            max_upload_bytes=1024,
        )
        self.inbox = self.config.inbox
        self.inbox.mkdir(parents=True)

        # Keep a stalled upload from holding the suite for the real deadline.
        self.addCleanup(setattr, server.BridgeHandler, "timeout", server.BridgeHandler.timeout)
        server.BridgeHandler.timeout = 1

        self.server = server.build_server(self.config, token=TOKEN, port=0)
        self.addCleanup(self.server.server_close)
        Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response, response.read().decode("utf-8", "replace")
        finally:
            connection.close()

    def get(self, path):
        response, body = self.request("GET", path)
        return response.status, body


class AuthTests(ServerCase):
    def test_every_route_needs_the_token(self):
        for method, path in (
            ("GET", "/"),
            ("GET", "/transcript.txt"),
            ("POST", "/send?name=note.txt"),
        ):
            with self.subTest(path=path):
                response, _ = self.request(method, path, body=b"x")

                self.assertEqual(response.status, 404)

    def test_a_wrong_token_is_refused(self):
        self.assertEqual(self.get("/?k=wrong")[0], 404)
        self.assertEqual(self.get(f"/?k={TOKEN}x")[0], 404)

    def test_an_unknown_route_is_refused_even_with_the_token(self):
        self.assertEqual(self.get(f"/etc/passwd?k={TOKEN}")[0], 404)
        self.assertEqual(self.get(f"/../token?k={TOKEN}")[0], 404)

    def test_the_token_file_is_created_private(self):
        path = self.root / "generated-token"
        token = server.load_token(path)

        self.assertTrue(token)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(server.load_token(path), token)


class PageTests(ServerCase):
    def test_serves_the_composer_and_the_transcript_view(self):
        status, body = self.get(f"/?k={TOKEN}")

        self.assertEqual(status, 200)
        self.assertIn('id="body"', body)
        self.assertIn('id="text"', body)
        self.assertIn('id="files"', body)
        self.assertIn("/transcript.txt?k=", body)

    def test_injects_the_configured_title_and_labels(self):
        _, body = self.get(f"/?k={TOKEN}")

        self.assertIn("Night Shift", body)
        self.assertIn('const YOU = "ME"', body)
        self.assertIn('const AGENT = "BOT"', body)

    def test_never_writes_the_token_into_the_page(self):
        _, body = self.get(f"/?k={TOKEN}")

        self.assertNotIn(TOKEN, body)

    def test_sends_the_privacy_headers(self):
        response, _ = self.request("GET", f"/?k={TOKEN}")

        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        self.assertEqual(response.getheader("Referrer-Policy"), "no-referrer")
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")


class TranscriptTests(ServerCase):
    def test_serves_the_mirrored_file(self):
        self.config.transcript_file.write_text("### ME  10:00", encoding="utf-8")

        status, body = self.get(f"/transcript.txt?k={TOKEN}")

        self.assertEqual(status, 200)
        self.assertIn("### ME  10:00", body)

    def test_survives_a_missing_mirror(self):
        status, body = self.get(f"/transcript.txt?k={TOKEN}")

        self.assertEqual(status, 200)
        self.assertIn("has not written", body)


class UploadTests(ServerCase):
    def send(self, name, body=b"payload", headers=None):
        return self.request("POST", f"/send?k={TOKEN}&name={name}", body, headers)

    def test_stores_the_body_in_the_inbox(self):
        response, _ = self.send("note.txt", b"what I sent")

        self.assertEqual(response.status, 200)
        self.assertEqual((self.inbox / "note.txt").read_text(encoding="utf-8"), "what I sent")

    def test_the_stored_file_is_private(self):
        self.send("note.txt")

        self.assertEqual((self.inbox / "note.txt").stat().st_mode & 0o777, 0o600)

    def test_refuses_an_unsafe_name(self):
        for name in ("../escape.txt", "%2e%2e%2fescape", ".hidden", ""):
            with self.subTest(name=name):
                response, _ = self.send(name)

                self.assertEqual(response.status, 400)
        self.assertEqual(list(self.inbox.iterdir()), [])

    def test_refuses_a_body_over_the_limit(self):
        response, _ = self.request(
            "POST",
            f"/send?k={TOKEN}&name=big.bin",
            body=b"",
            headers={"Content-Length": str(4096)},
        )

        self.assertEqual(response.status, 413)
        self.assertFalse((self.inbox / "big.bin").exists())

    def test_refuses_a_malformed_content_length(self):
        response, _ = self.request(
            "POST",
            f"/send?k={TOKEN}&name=note.txt",
            body=b"x",
            headers={"Content-Length": "twelve"},
        )

        self.assertEqual(response.status, 411)

    def test_refuses_an_empty_body(self):
        response, _ = self.request(
            "POST", f"/send?k={TOKEN}&name=empty.txt", body=b"", headers={}
        )

        self.assertEqual(response.status, 400)
        self.assertEqual(list(self.inbox.iterdir()), [])

    def test_refuses_once_the_inbox_is_full(self):
        for index in range(3):
            self.send(f"note{index}.txt")

        response, _ = self.send("one-too-many.txt")

        self.assertEqual(response.status, 429)
        self.assertFalse((self.inbox / "one-too-many.txt").exists())

    def test_leaves_no_partial_file_behind_when_the_body_never_arrives(self):
        response, _ = self.request(
            "POST",
            f"/send?k={TOKEN}&name=short.bin",
            body=b"ab",
            headers={"Content-Length": "64"},
        )

        self.assertEqual(response.status, 408)
        self.assertEqual(list(self.inbox.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

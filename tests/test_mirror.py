import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from backchannel import mirror
from backchannel.config import Config
from backchannel.models import TranscriptError


def record(kind, text, timestamp):
    return {
        "type": kind,
        "timestamp": timestamp,
        "message": {"role": kind, "content": text},
    }


class MirrorCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.config = Config(
            workspace=self.project,
            share_root=self.root / "share",
            token_file=self.root / "token",
            timezone="UTC",
        )

    def session(self, name, records):
        path = self.project / name
        path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
        return path


class RunTests(MirrorCase):
    def test_writes_the_rendered_transcript(self):
        self.session("a.jsonl", [record("user", "hello", "2026-08-28T20:05:00.000Z")])

        mirror.run(self.config, once=True, log=io.StringIO())

        self.assertEqual(
            self.config.transcript_file.read_text(encoding="utf-8"),
            "### YOU  20:05\n\nhello\n",
        )

    def test_picks_the_most_recently_written_session(self):
        old = self.session("old.jsonl", [record("user", "stale", "2026-08-28T20:05:00.000Z")])
        self.session("new.jsonl", [record("user", "fresh", "2026-08-28T20:06:00.000Z")])
        os.utime(old, (1, 1))

        mirror.run(self.config, once=True, log=io.StringIO())

        body = self.config.transcript_file.read_text(encoding="utf-8")
        self.assertIn("fresh", body)
        self.assertNotIn("stale", body)

    def test_the_transcript_file_is_private(self):
        self.session("a.jsonl", [record("user", "hello", "2026-08-28T20:05:00.000Z")])

        mirror.run(self.config, once=True, log=io.StringIO())

        self.assertEqual(self.config.transcript_file.stat().st_mode & 0o777, 0o600)

    def test_reports_a_workspace_with_no_session_instead_of_crashing(self):
        log = io.StringIO()

        mirror.run(self.config, once=True, log=log)

        self.assertIn("no Claude Code project directory", log.getvalue())
        self.assertFalse(self.config.transcript_file.exists())


class ZoneTests(unittest.TestCase):
    def test_local_means_no_explicit_zone(self):
        self.assertIsNone(mirror.zone("local"))
        self.assertIsNone(mirror.zone(""))

    def test_resolves_a_named_zone(self):
        self.assertIsNotNone(mirror.zone("America/Sao_Paulo"))

    def test_reports_an_unknown_zone(self):
        with self.assertRaises(TranscriptError):
            mirror.zone("Mars/Olympus")


class WriteAtomicTests(unittest.TestCase):
    def test_leaves_no_temporary_file_behind(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "transcript.txt"

            mirror.write_atomic(target, "body")

            self.assertEqual(target.read_text(encoding="utf-8"), "body")
            self.assertEqual([p.name for p in target.parent.iterdir()], ["transcript.txt"])


if __name__ == "__main__":
    unittest.main()

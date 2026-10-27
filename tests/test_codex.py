import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backchannel.models import AGENT, YOU
from backchannel.transcript import codex


def user(text, timestamp="2026-08-28T20:05:00Z"):
    return {
        "type": "event_msg",
        "timestamp": timestamp,
        "payload": {
            "type": "item_completed",
            "item": {"type": "UserMessage", "content": [{"type": "text", "text": text}]},
        },
    }


def assistant(text, phase="final_answer", timestamp="2026-08-28T20:06:00Z"):
    return {
        "type": "response_item",
        "timestamp": timestamp,
        "payload": {
            "type": "message",
            "role": "assistant",
            "phase": phase,
            "content": [{"type": "output_text", "text": text}],
        },
    }


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def parse(self, records):
        path = self.root / "rollout-2026-08-28-abc.jsonl"
        path.write_text(
            "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
        )
        return codex.parse(path)

    def test_reads_both_speakers(self):
        messages = self.parse([user("start the job"), assistant("started")])

        self.assertEqual([m.speaker for m in messages], [YOU, AGENT])
        self.assertEqual([m.text for m in messages], ["start the job", "started"])

    def test_keeps_commentary_and_the_final_answer(self):
        messages = self.parse(
            [assistant("thinking out loud", phase="commentary"), assistant("done")]
        )

        self.assertEqual([m.text for m in messages], ["thinking out loud", "done"])

    def test_ignores_other_assistant_phases(self):
        self.assertEqual(self.parse([assistant("draft", phase="reasoning")]), [])

    def test_ignores_records_that_are_not_messages(self):
        self.assertEqual(
            self.parse(
                [
                    {
                        "type": "event_msg",
                        "timestamp": "2026-08-28T20:05:00Z",
                        "payload": {"type": "token_count", "count": 12},
                    },
                    {
                        "type": "response_item",
                        "timestamp": "2026-08-28T20:05:00Z",
                        "payload": {"type": "function_call", "name": "shell"},
                    },
                ]
            ),
            [],
        )

    def test_joins_split_content_parts(self):
        record = assistant("")
        record["payload"]["content"] = [
            {"type": "output_text", "text": "one "},
            {"type": "reasoning_text", "text": "hidden"},
            {"type": "output_text", "text": "two"},
        ]

        self.assertEqual([m.text for m in self.parse([record])], ["one two"])

    def test_survives_malformed_lines(self):
        path = self.root / "rollout-2026-08-28-abc.jsonl"
        path.write_text(
            json.dumps(user("kept")) + "\nnot json at all\n[1,2,3]\n", encoding="utf-8"
        )

        self.assertEqual([m.text for m in codex.parse(path)], ["kept"])


class SessionsTests(unittest.TestCase):
    def test_global_discovery_only_returns_the_requested_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "wanted"
            workspace.mkdir()
            sessions = root / "sessions"
            sessions.mkdir()
            wanted = sessions / "rollout-wanted.jsonl"
            unrelated = sessions / "rollout-unrelated.jsonl"
            for path, cwd in ((wanted, workspace), (unrelated, root / "other")):
                path.write_text(
                    json.dumps({"type": "session_meta", "payload": {"cwd": str(cwd)}}) + "\n",
                    encoding="utf-8",
                )

            with patch.object(codex, "SESSIONS_DIR", sessions):
                self.assertEqual(codex.sessions(workspace), [wanted])
                self.assertEqual(codex.sessions(root / "missing"), [])

    def test_global_discovery_ignores_missing_or_invalid_workspace_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "project"
            workspace.mkdir()
            sessions = root / "sessions"
            sessions.mkdir()
            for index, body in enumerate(
                ("not json", "null", "{}", '{"type":"session_meta","payload":null}')
            ):
                (sessions / f"rollout-{index}.jsonl").write_text(body, encoding="utf-8")

            with patch.object(codex, "SESSIONS_DIR", sessions):
                self.assertEqual(codex.sessions(workspace), [])

    def test_a_rollout_file_is_used_directly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rollout-2026-08-28-abc.jsonl"
            path.write_text("{}\n", encoding="utf-8")

            self.assertEqual(codex.sessions(path), [path])

    def test_finds_rollouts_nested_under_a_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            nested = Path(directory) / "2026" / "08"
            nested.mkdir(parents=True)
            path = nested / "rollout-2026-08-28-abc.jsonl"
            path.write_text("{}\n", encoding="utf-8")

            self.assertEqual(codex.sessions(Path(directory)), [path])


if __name__ == "__main__":
    unittest.main()

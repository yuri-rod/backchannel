import json
from pathlib import Path
import tempfile
import unittest

from backchannel.models import AGENT, YOU, TranscriptError
from backchannel.transcript import claude_code


def user(text, timestamp="2026-08-28T20:05:00.000Z", **extra):
    return {
        "type": "user",
        "timestamp": timestamp,
        "message": {"role": "user", "content": text},
        **extra,
    }


def assistant(blocks, timestamp="2026-08-28T20:06:00.000Z", **extra):
    return {
        "type": "assistant",
        "timestamp": timestamp,
        "message": {"role": "assistant", "content": blocks},
        **extra,
    }


def session(records, directory):
    path = Path(directory) / "session.jsonl"
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )
    return path


class ParseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def parse(self, records):
        return claude_code.parse(session(records, self.root))

    def test_reads_both_speakers_in_order(self):
        messages = self.parse(
            [user("which block?"), assistant([{"type": "text", "text": "this one"}])]
        )

        self.assertEqual([m.speaker for m in messages], [YOU, AGENT])
        self.assertEqual([m.text for m in messages], ["which block?", "this one"])

    def test_keeps_only_prose_blocks(self):
        messages = self.parse(
            [
                assistant(
                    [
                        {"type": "thinking", "thinking": "internal reasoning"},
                        {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                        {"type": "text", "text": "listed the files"},
                    ]
                ),
                user([{"type": "tool_result", "content": "raw output"}]),
            ]
        )

        body = "\n".join(m.text for m in messages)
        self.assertIn("listed the files", body)
        self.assertNotIn("internal reasoning", body)
        self.assertNotIn("raw output", body)
        self.assertNotIn("ls", body)

    def test_skips_records_that_carry_no_prose(self):
        self.assertEqual(self.parse([user("   "), assistant([])]), [])

    def test_survives_a_truncated_last_line(self):
        path = self.root / "session.jsonl"
        path.write_text(
            json.dumps(user("first")) + "\n" + json.dumps(assistant([]))[:20],
            encoding="utf-8",
        )

        self.assertEqual([m.text for m in claude_code.parse(path)], ["first"])


class RedactionTests(unittest.TestCase):
    """The page is public. Anything the harness injects has to die here."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def parse(self, records):
        return "\n".join(m.text for m in claude_code.parse(session(records, self.root)))

    def test_drops_system_reminders(self):
        body = self.parse(
            [user("real question<system-reminder>\nhouse rule\n</system-reminder>")]
        )

        self.assertIn("real question", body)
        self.assertNotIn("house rule", body)

    def test_drops_a_multiline_reminder_with_markup_inside(self):
        body = self.parse(
            [
                user(
                    "ask<system-reminder>\nAPI_KEY=sk-secret\n"
                    "path: /home/someone/private\n</system-reminder>after"
                )
            ]
        )

        self.assertNotIn("sk-secret", body)
        self.assertNotIn("private", body)
        self.assertIn("ask", body)
        self.assertIn("after", body)

    def test_drops_every_harness_tag(self):
        tags = [
            "command-name",
            "command-message",
            "command-args",
            "local-command-stdout",
            "local-command-caveat",
            "bash-input",
            "bash-stdout",
            "bash-stderr",
        ]
        for tag in tags:
            with self.subTest(tag=tag):
                body = self.parse([user(f"keep<{tag}>secret-{tag}</{tag}>me")])

                self.assertNotIn(f"secret-{tag}", body)
                self.assertIn("keep", body)
                self.assertIn("me", body)

    def test_drops_sidechain_and_meta_records(self):
        body = self.parse(
            [
                user("<command-name>/model</command-name>", isMeta=True),
                assistant([{"type": "text", "text": "subagent chatter"}], isSidechain=True),
                user("visible"),
            ]
        )

        self.assertEqual(body, "visible")

    def test_redacts_inside_a_block_list_too(self):
        body = self.parse(
            [assistant([{"type": "text", "text": "a<bash-stdout>leak</bash-stdout>b"}])]
        )

        self.assertNotIn("leak", body)


class ProjectDirTests(unittest.TestCase):
    def test_slug_matches_the_claude_code_convention(self):
        self.assertEqual(
            claude_code.slug("/Users/someone/work/my-project"),
            "-Users-someone-work-my-project",
        )
        self.assertEqual(
            claude_code.slug("/Users/someone/dot.name_here"),
            "-Users-someone-dot-name-here",
        )

    def test_a_directory_of_sessions_is_used_directly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "session.jsonl").write_text("{}\n", encoding="utf-8")

            self.assertEqual(claude_code.project_dir(root), root)

    def test_reports_a_workspace_with_no_project_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TranscriptError):
                claude_code.project_dir(Path(directory) / "never-opened")


if __name__ == "__main__":
    unittest.main()

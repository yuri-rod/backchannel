from pathlib import Path
import tempfile
import unittest

from backchannel import config as configuration


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "config.toml"

    def write(self, body):
        self.path.write_text(body, encoding="utf-8")
        return self.path

    def test_defaults_apply_when_there_is_no_file(self):
        settings = configuration.load(self.path, environ={})

        self.assertEqual(settings.agent, "claude-code")
        self.assertEqual(settings.host, "127.0.0.1")
        self.assertEqual(settings.port, 8686)
        self.assertEqual(settings.you_label, "YOU")

    def test_reads_every_section(self):
        settings = configuration.load(
            self.write(
                """
                [bridge]
                agent = "codex"
                workspace = "/tmp/work"
                title = "Night Shift"
                you_label = "ME"
                agent_label = "BOT"

                [server]
                port = 9000
                share_root = "/tmp/share"

                [mirror]
                poll_seconds = 0.5
                timezone = "America/Sao_Paulo"
                """
            ),
            environ={},
        )

        self.assertEqual(settings.agent, "codex")
        self.assertEqual(settings.workspace, Path("/tmp/work"))
        self.assertEqual(settings.title, "Night Shift")
        self.assertEqual(settings.agent_label, "BOT")
        self.assertEqual(settings.port, 9000)
        self.assertEqual(settings.poll_seconds, 0.5)
        self.assertEqual(settings.timezone, "America/Sao_Paulo")

    def test_environment_overrides_the_file(self):
        settings = configuration.load(
            self.write("[server]\nport = 9000\n"),
            environ={"BACKCHANNEL_PORT": "7777"},
        )

        self.assertEqual(settings.port, 7777)

    def test_expands_the_home_shortcut_in_paths(self):
        settings = configuration.load(
            self.write('[server]\nshare_root = "~/somewhere"\n'), environ={}
        )

        self.assertTrue(settings.share_root.is_absolute())
        self.assertTrue(str(settings.share_root).endswith("/somewhere"))

    def test_derives_the_inbox_and_transcript_from_the_share_root(self):
        settings = configuration.load(
            self.write('[server]\nshare_root = "/tmp/share"\n'), environ={}
        )

        self.assertEqual(settings.inbox, Path("/tmp/share/inbox"))
        self.assertEqual(settings.transcript_file, Path("/tmp/share/transcript.txt"))

    def test_rejects_a_typo_in_a_setting_name(self):
        with self.assertRaises(configuration.ConfigError) as caught:
            configuration.load(self.write("[server]\nprot = 9000\n"), environ={})

        self.assertIn("server.prot", str(caught.exception))

    def test_rejects_values_outside_their_range(self):
        cases = [
            ("[server]\nport = 0\n", "port"),
            ("[mirror]\npoll_seconds = 0\n", "poll_seconds"),
            ("[server]\nmax_upload_bytes = 0\n", "max_upload_bytes"),
            ("[bridge]\nyou_label = '  '\n", "labels"),
        ]
        for body, expected in cases:
            with self.subTest(body=body):
                with self.assertRaises(configuration.ConfigError) as caught:
                    configuration.load(self.write(body), environ={})

                self.assertIn(expected, str(caught.exception))

    def test_rejects_a_non_numeric_port(self):
        with self.assertRaises(configuration.ConfigError):
            configuration.load(self.path, environ={"BACKCHANNEL_PORT": "eight"})

    def test_rejects_a_broken_file(self):
        with self.assertRaises(configuration.ConfigError):
            configuration.load(self.write("[server\nport = 1\n"), environ={})


if __name__ == "__main__":
    unittest.main()

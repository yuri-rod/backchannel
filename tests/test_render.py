from datetime import timedelta, timezone
import unittest

from backchannel.models import AGENT, YOU, Message
from backchannel.render import render

SAO_PAULO = timezone(timedelta(hours=-3))


class RenderTests(unittest.TestCase):
    def test_writes_a_heading_per_message(self):
        body = render(
            [
                Message(YOU, "which block?", "2026-08-28T20:05:00.000Z"),
                Message(AGENT, "this one", "2026-08-28T20:06:00.000Z"),
            ],
            tz=SAO_PAULO,
        )

        self.assertEqual(
            body.splitlines(),
            [
                "### YOU  17:05",
                "",
                "which block?",
                "",
                "### AGENT  17:06",
                "",
                "this one",
            ],
        )

    def test_uses_the_configured_labels(self):
        body = render(
            [Message(YOU, "hi", "2026-08-28T20:05:00.000Z")],
            you_label="ME",
            agent_label="BOT",
            tz=SAO_PAULO,
        )

        self.assertTrue(body.startswith("### ME  17:05"))

    def test_falls_back_when_the_timestamp_is_unusable(self):
        for stamp in (None, "", "not-a-date", 17):
            with self.subTest(stamp=stamp):
                body = render([Message(YOU, "hi", stamp)])

                self.assertIn("--:--", body)

    def test_drops_empty_messages(self):
        self.assertEqual(render([Message(YOU, "", "2026-08-28T20:05:00.000Z")]), "")


if __name__ == "__main__":
    unittest.main()

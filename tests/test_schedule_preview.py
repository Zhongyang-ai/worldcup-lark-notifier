import os
import tempfile
import unittest
from datetime import datetime

from worldcup_bot.config import Config
from worldcup_bot.models import Match
from worldcup_bot.service import _daily_schedule_preview
from worldcup_bot.store import Store


class Notifier:
    def __init__(self):
        self.messages = []

    def send(self, message):
        self.messages.append(message)


class SchedulePreviewTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp()
        os.close(handle)
        self.store = Store(self.path)
        self.notifier = Notifier()
        self.config = Config("x", "", "Asia/Singapore", 8, 60, 12, True, True, True, False, 9, 22, "", "deepseek-v4-pro", 300, "high", True, self.path, 8080, "INFO")

    def tearDown(self):
        os.unlink(self.path)

    def test_sends_tomorrow_matches_in_singapore_time_once(self):
        now = datetime.fromisoformat("2026-06-13T22:05:00+08:00")
        matches = [
            Match("1", "Brazil", "Morocco", 0, 0, "pre", "", "", "", "2026-06-14T19:00:00Z"),
            Match("2", "Qatar", "Switzerland", 0, 0, "pre", "", "", "", "2026-06-13T19:00:00Z"),
        ]

        _daily_schedule_preview(self.config, self.store, self.notifier, matches, now)
        _daily_schedule_preview(self.config, self.store, self.notifier, matches, now)

        self.assertEqual(1, len(self.notifier.messages))
        self.assertIn("2026-06-14", self.notifier.messages[0])
        self.assertIn("03:00  Qatar vs Switzerland", self.notifier.messages[0])
        self.assertNotIn("Brazil", self.notifier.messages[0])

    def test_sends_no_match_message(self):
        now = datetime.fromisoformat("2026-06-13T22:05:00+08:00")
        _daily_schedule_preview(self.config, self.store, self.notifier, [], now)
        self.assertIn("明日无比赛", self.notifier.messages[0])


if __name__ == "__main__":
    unittest.main()

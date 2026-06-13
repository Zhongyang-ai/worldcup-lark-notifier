import os
import tempfile
import unittest
from dataclasses import replace

from worldcup_bot.config import Config
from worldcup_bot.engine import EventEngine
from worldcup_bot.models import Match, MatchEvent
from worldcup_bot.store import Store


def config(path):
    return Config("x", "", "Asia/Singapore", 8, 60, 12, True, True, True, False, 9, 22, "", "deepseek-v4-pro", True, path, 8080, "INFO")


class EventEngineTest(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp()
        os.close(handle)
        self.messages = []
        self.store = Store(self.path)
        self.engine = EventEngine(config(self.path), self.store, self.messages.append)
        self.base = Match("1", "Mexico", "South Africa", 0, 0, "pre", "STATUS_SCHEDULED", "Scheduled", "", "x")

    def tearDown(self):
        os.unlink(self.path)

    def test_bootstrap_does_not_send_old_events(self):
        goal = MatchEvent("goal:Mexico:10:A", "goal", "10'", "Mexico", "A")
        self.engine.process(replace(self.base, home_score=1, state="in", events=[goal]))
        self.assertEqual([], self.messages)

    def test_goal_is_sent_once(self):
        self.engine.process(self.base)
        live = replace(self.base, state="in", status_name="STATUS_IN_PROGRESS")
        self.engine.process(live)
        goal = MatchEvent("goal:Mexico:10:A", "goal", "10'", "Mexico", "A")
        scored = replace(live, home_score=1, events=[goal])
        self.engine.process(scored)
        self.engine.process(scored)
        self.assertEqual(2, len(self.messages))
        self.assertIn("开赛", self.messages[0])
        self.assertIn("进球", self.messages[1])

    def test_score_rollback_sends_correction(self):
        self.engine.process(replace(self.base, home_score=1, state="in"))
        self.engine.process(replace(self.base, home_score=0, state="in"))
        self.assertEqual(1, len(self.messages))
        self.assertIn("比分修正", self.messages[0])

    def test_goal_uses_event_score_not_stale_match_score(self):
        self.engine.process(self.base)
        goal = MatchEvent("goal:Mexico:10:A", "goal", "10'", "Mexico", "A", event_id="event-1", home_score=1, away_score=0)
        self.engine.process(replace(self.base, state="in", events=[goal]))
        self.assertIn("Mexico 1-0 South Africa", self.messages[-1])


if __name__ == "__main__":
    unittest.main()

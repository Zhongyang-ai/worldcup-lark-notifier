import unittest
from unittest.mock import patch

from worldcup_bot.models import Match
from worldcup_bot.provider import EspnProvider


class ProviderTest(unittest.TestCase):
    def test_summary_score_overrides_stale_scoreboard(self):
        stale = Match("1", "Canada", "Bosnia", 0, 0, "in", "STATUS_FIRST_HALF", "First Half", "21'", "x")
        summary = {
            "keyEvents": [
                {
                    "id": "goal-1",
                    "scoringPlay": True,
                    "shootout": False,
                    "type": {"type": "goal"},
                    "team": {"displayName": "Bosnia"},
                    "clock": {"displayValue": "21'"},
                    "participants": [{"athlete": {"displayName": "Jovo Lukic"}}],
                }
            ],
            "header": {
                "competitions": [
                    {
                        "status": {
                            "displayClock": "22'",
                            "type": {"state": "in", "name": "STATUS_FIRST_HALF", "description": "First Half"},
                        },
                        "competitors": [
                            {"homeAway": "home", "score": "0"},
                            {"homeAway": "away", "score": "1"},
                        ],
                        "details": [],
                    }
                ]
            }
        }
        provider = EspnProvider()
        with patch.object(provider, "_get", return_value=summary):
            current = provider.fetch_details(stale)

        self.assertEqual((0, 1), (current.home_score, current.away_score))
        self.assertEqual("22'", current.clock)
        self.assertEqual(1, len(current.events))
        self.assertEqual("goal-1", current.events[0].event_id)
        self.assertEqual((0, 1), (current.events[0].home_score, current.events[0].away_score))

    def test_each_goal_has_its_score_and_stable_id(self):
        events = EspnProvider._parse_key_events(
            [
                {"id": "a", "scoringPlay": True, "team": {"displayName": "USA"}, "clock": {"displayValue": "7'"}, "participants": []},
                {"id": "b", "scoringPlay": True, "team": {"displayName": "USA"}, "clock": {"displayValue": "31'"}, "participants": []},
                {"id": "c", "scoringPlay": True, "team": {"displayName": "Paraguay"}, "clock": {"displayValue": "73'"}, "participants": []},
            ],
            "USA",
            "Paraguay",
        )
        self.assertEqual(["a", "b", "c"], [event.event_id for event in events])
        self.assertEqual([(1, 0), (2, 0), (2, 1)], [(event.home_score, event.away_score) for event in events])


if __name__ == "__main__":
    unittest.main()

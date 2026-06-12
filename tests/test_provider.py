import unittest
from unittest.mock import patch

from worldcup_bot.models import Match
from worldcup_bot.provider import EspnProvider


class ProviderTest(unittest.TestCase):
    def test_summary_score_overrides_stale_scoreboard(self):
        stale = Match("1", "Canada", "Bosnia", 0, 0, "in", "STATUS_FIRST_HALF", "First Half", "21'", "x")
        summary = {
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
                        "details": [
                            {
                                "scoringPlay": True,
                                "team": {"displayName": "Bosnia"},
                                "clock": {"displayValue": "21'"},
                                "participants": [{"athlete": {"displayName": "Jovo Lukic"}}],
                            }
                        ],
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


if __name__ == "__main__":
    unittest.main()

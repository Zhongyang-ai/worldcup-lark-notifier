import unittest

from worldcup_bot.prediction import DeepSeekPredictor


class PredictionTest(unittest.TestCase):
    def test_formats_prediction(self):
        text = DeepSeekPredictor._format(
            {
                "predictions": [
                    {
                        "home": "Brazil",
                        "away": "Morocco",
                        "home_win": 55,
                        "draw": 25,
                        "away_win": 20,
                        "predicted_score": "2-1",
                        "over_under_view": "偏大",
                        "btts_view": "是",
                        "confidence": "中",
                        "key_factors": ["市场支持主队"],
                        "risks": ["首发未知"],
                    }
                ]
            }
        )
        self.assertIn("55% / 25% / 20%", text)
        self.assertIn("2-1", text)
        self.assertIn("不构成投注建议", text)


if __name__ == "__main__":
    unittest.main()

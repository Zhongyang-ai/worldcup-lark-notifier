#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def load_env() -> None:
    path = PROJECT_ROOT / ".env"
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("date", help="Schedule date in configured timezone, YYYY-MM-DD")
    args = parser.parse_args()
    load_env()

    from worldcup_bot.config import Config
    from worldcup_bot.lark import LarkNotifier
    from worldcup_bot.prediction import DeepSeekPredictor
    from worldcup_bot.provider import EspnProvider

    config = Config.from_env()
    tz = ZoneInfo(config.timezone)
    target = datetime.strptime(args.date, "%Y-%m-%d").date()
    provider = EspnProvider(config.request_timeout_seconds)
    matches = provider.fetch_matches(datetime(target.year, target.month, target.day, 12, tzinfo=tz))
    rows = []
    for match in matches:
        if not match.start_time:
            continue
        kickoff = datetime.fromisoformat(match.start_time.replace("Z", "+00:00")).astimezone(tz)
        if kickoff.date() == target:
            rows.append((kickoff, match))
    rows.sort(key=lambda item: item[0])

    upcoming = [(kickoff, match) for kickoff, match in rows if match.state == "pre"]
    if not upcoming:
        raise RuntimeError("No pre-match fixtures available for prediction")

    contexts = [provider.fetch_prediction_context(match) for _, match in upcoming]
    predictor = DeepSeekPredictor(config.deepseek_api_key, config.deepseek_model)
    analysis, usage = predictor.predict(contexts)
    lines = [f"📅 {target:%-m月%-d日}世界杯赛程与 AI 预测（新加坡时间）"]
    lines.extend(f"{kickoff:%H:%M}  {match.home} vs {match.away}" for kickoff, match in rows)
    message = "\n".join(lines) + "\n\n" + analysis
    LarkNotifier(config.lark_webhook_url, config.lark_secret).send(message)
    print(json.dumps({"sent": True, "matches": len(rows), "predicted": len(upcoming), "usage": usage}, ensure_ascii=False))


if __name__ == "__main__":
    main()

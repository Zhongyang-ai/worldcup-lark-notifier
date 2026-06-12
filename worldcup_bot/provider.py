from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import Match, MatchEvent


class EspnProvider:
    BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world"

    def __init__(self, timeout: int = 12):
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, str]) -> dict:
        url = f"{self.BASE}/{path}?{urlencode(params)}"
        return self._get_url(url)

    def _get_url(self, url: str) -> dict:
        request = Request(url, headers={"User-Agent": "worldcup-lark-bot/1.0"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def fetch_matches(self, now: datetime | None = None) -> list[Match]:
        now = now or datetime.now(timezone.utc)
        matches: dict[str, Match] = {}
        for offset in (-1, 0, 1):
            date = (now + timedelta(days=offset)).strftime("%Y%m%d")
            data = self._get("scoreboard", {"dates": date, "limit": "100"})
            for raw in data.get("events", []):
                match = self._parse_match(raw)
                matches[match.match_id] = match

        result = []
        for match in matches.values():
            if match.is_live:
                result.append(self.fetch_details(match))
            else:
                result.append(match)
        return sorted(result, key=lambda item: item.start_time)

    def fetch_details(self, match: Match) -> Match:
        data = self._get("summary", {"event": match.match_id})
        details = data.get("header", {}).get("competitions", [{}])[0].get("details", [])
        events: list[MatchEvent] = []
        for detail in details:
            event = self._parse_detail(detail)
            if event:
                events.append(event)
        return Match(**{**match.__dict__, "events": events})

    def fetch_prediction_context(self, match: Match) -> dict:
        data = self._get("summary", {"event": match.match_id})
        competition = data.get("header", {}).get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        records = {}
        team_ids = {}
        for item in competitors:
            name = item.get("team", {}).get("displayName", "Unknown")
            team_ids[name] = str(item.get("team", {}).get("id", ""))
            records[name] = [record.get("summary") for record in item.get("record", []) if record.get("summary")]

        odds = data.get("odds", [])
        market = self._compact_odds(odds[0]) if odds else None
        news_data = data.get("news") or []
        news_items = news_data.get("articles", []) if isinstance(news_data, dict) else news_data
        news = []
        team_names = {match.home.lower(), match.away.lower()}
        for item in news_items:
            headline = item.get("headline")
            description = item.get("description")
            categories = {
                str(category.get("description", "")).lower()
                for category in item.get("categories", [])
                if category.get("type") == "team"
            }
            relevant = bool(team_names & categories)
            if headline and relevant:
                news.append({"headline": headline, "description": description})
            if len(news) >= 6:
                break

        injuries = []
        for group in data.get("injuries", []) or []:
            team = group.get("team", {}).get("displayName", "Unknown")
            for injury in group.get("injuries", []):
                athlete = injury.get("athlete", {}).get("displayName", "Unknown")
                status = injury.get("status", injury.get("type", {}).get("description", "Unknown"))
                injuries.append({"team": team, "player": athlete, "status": status})

        head_to_head = []
        for game in (data.get("headToHeadGames", []) or [])[:5]:
            competition_data = game.get("competitions", [{}])[0]
            sides = competition_data.get("competitors", [])
            if len(sides) >= 2:
                head_to_head.append(
                    {
                        "date": game.get("date"),
                        "teams": [
                            {
                                "name": side.get("team", {}).get("displayName"),
                                "score": side.get("score"),
                            }
                            for side in sides
                        ],
                    }
                )

        return {
            "match_id": match.match_id,
            "home": match.home,
            "away": match.away,
            "kickoff_utc": match.start_time,
            "venue": competition.get("venue", {}).get("fullName") or data.get("gameInfo", {}).get("venue", {}).get("fullName"),
            "records": records,
            "recent_results": {
                name: self._fetch_recent_results(team_id, match.start_time)
                for name, team_id in team_ids.items()
                if team_id
            },
            "market_odds": market,
            "injuries": injuries,
            "recent_news": news,
            "head_to_head": head_to_head,
            "data_limitations": "Only listed facts are verified. Missing fields mean unavailable, not none.",
        }

    def _fetch_recent_results(self, team_id: str, before: str, limit: int = 6) -> list[dict]:
        season = before[:4]
        url = (
            "https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams/"
            f"{team_id}/schedule?{urlencode({'season': season})}"
        )
        data = self._get_url(url)
        cutoff = datetime.fromisoformat(before.replace("Z", "+00:00"))
        results = []
        for event in data.get("events", []):
            event_date = datetime.fromisoformat(str(event.get("date", "")).replace("Z", "+00:00"))
            if event_date >= cutoff:
                continue
            competition = event.get("competitions", [{}])[0]
            sides = competition.get("competitors", [])
            if len(sides) < 2 or any(self._score_value(side.get("score")) is None for side in sides):
                continue
            results.append(
                {
                    "date": event.get("date"),
                    "teams": [
                        {
                            "name": side.get("team", {}).get("displayName"),
                            "score": self._score_value(side.get("score")),
                            "winner": side.get("winner"),
                        }
                        for side in sides
                    ],
                }
            )
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _score_value(score) -> str | None:
        if isinstance(score, dict):
            value = score.get("displayValue", score.get("value"))
        else:
            value = score
        return str(value) if value is not None else None

    @staticmethod
    def _compact_odds(raw: dict) -> dict:
        moneyline = raw.get("moneyline", {})

        def line(side: str, point: str) -> str | None:
            value = moneyline.get(side, {}).get(point, {}).get("odds")
            return str(value) if value is not None else None

        return {
            "provider": raw.get("provider", {}).get("name"),
            "spread": raw.get("details"),
            "total": raw.get("overUnder"),
            "home_moneyline_open": line("home", "open"),
            "home_moneyline_current": line("home", "close") or raw.get("homeTeamOdds", {}).get("moneyLine"),
            "draw_moneyline_open": line("draw", "open"),
            "draw_moneyline_current": line("draw", "close") or raw.get("drawOdds", {}).get("moneyLine"),
            "away_moneyline_open": line("away", "open"),
            "away_moneyline_current": line("away", "close") or raw.get("awayTeamOdds", {}).get("moneyLine"),
            "over_odds": raw.get("overOdds"),
            "under_odds": raw.get("underOdds"),
        }

    @staticmethod
    def _parse_match(raw: dict) -> Match:
        competition = raw.get("competitions", [{}])[0]
        competitors = competition.get("competitors", [])
        by_side = {item.get("homeAway"): item for item in competitors}
        home = by_side.get("home", {})
        away = by_side.get("away", {})
        status = competition.get("status", raw.get("status", {}))
        status_type = status.get("type", {})
        return Match(
            match_id=str(raw["id"]),
            home=home.get("team", {}).get("displayName", "Home"),
            away=away.get("team", {}).get("displayName", "Away"),
            home_score=int(home.get("score") or 0),
            away_score=int(away.get("score") or 0),
            state=status_type.get("state", "pre"),
            status_name=status_type.get("name", ""),
            status_text=status_type.get("description", status_type.get("detail", "")),
            clock=status.get("displayClock", ""),
            start_time=raw.get("date", competition.get("date", "")),
        )

    @staticmethod
    def _parse_detail(detail: dict) -> MatchEvent | None:
        is_goal = bool(detail.get("scoringPlay"))
        is_red = bool(detail.get("redCard"))
        if not is_goal and not is_red:
            return None
        team = detail.get("team", {}).get("displayName", "Unknown")
        participants = detail.get("participants", [])
        player = participants[0].get("athlete", {}).get("displayName", "") if participants else ""
        minute = detail.get("clock", {}).get("displayValue", "")
        flags = []
        if detail.get("penaltyKick"):
            flags.append("点球")
        if detail.get("ownGoal"):
            flags.append("乌龙球")
        kind = "goal" if is_goal else "red_card"
        fingerprint = ":".join([kind, team, minute, player])
        return MatchEvent(fingerprint, kind, minute, team, player, " / ".join(flags))

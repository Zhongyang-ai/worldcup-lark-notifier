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


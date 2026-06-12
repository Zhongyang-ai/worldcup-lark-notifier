from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MatchEvent:
    fingerprint: str
    kind: str
    minute: str
    team: str
    player: str = ""
    detail: str = ""


@dataclass(frozen=True)
class Match:
    match_id: str
    home: str
    away: str
    home_score: int
    away_score: int
    state: str
    status_name: str
    status_text: str
    clock: str
    start_time: str
    events: list[MatchEvent] = field(default_factory=list)

    @property
    def is_live(self) -> bool:
        return self.state == "in"

    @property
    def is_finished(self) -> bool:
        return self.state == "post"


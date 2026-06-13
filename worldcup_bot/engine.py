from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Config
from .models import Match
from .store import Store


class EventEngine:
    def __init__(self, config: Config, store: Store, send):
        self.config = config
        self.store = store
        self.send = send
        self.tz = ZoneInfo(config.timezone)

    def process(self, match: Match) -> None:
        previous = self.store.get_match(match.match_id)
        if previous is None:
            if self.config.send_existing_on_start and match.is_live:
                self._send_new_match_events(match)
            else:
                for event in match.events:
                    self.store.mark_sent(self._event_key(match, event.fingerprint))
            self.store.save_match(match)
            return

        self._status_changes(match, previous)
        self._send_new_match_events(match)
        self._score_correction(match, previous)
        self.store.save_match(match)

    def _status_changes(self, match: Match, previous: dict) -> None:
        old_state = previous["state"]
        old_status = previous["status_name"]
        if self.config.notify_kickoff and old_state == "pre" and match.state == "in":
            self._once(match, "kickoff", f"🏁 开赛\n{self._scoreline(match)}")
        if self.config.notify_halftime and old_status != match.status_name and "HALFTIME" in match.status_name:
            self._once(match, "halftime", f"⏸ 半场结束\n{self._scoreline(match)}")
        if old_state != "post" and match.is_finished:
            self._once(match, "fulltime", f"🏆 比赛结束\n{self._scoreline(match)}\n状态：{match.status_text}")

    def _send_new_match_events(self, match: Match) -> None:
        for event in match.events:
            key = self._event_key(match, event.event_id or event.fingerprint)
            legacy_key = self._event_key(match, event.fingerprint)
            if self.store.was_sent(key) or self.store.was_sent(legacy_key):
                if event.event_id and not self.store.was_sent(key):
                    self.store.mark_sent(key)
                continue
            if event.kind == "red_card" and not self.config.notify_red_card:
                self.store.mark_sent(key)
                continue
            if event.kind == "goal":
                extra = f"（{event.detail}）" if event.detail else ""
                player = event.player or "进球球员待更新"
                scoreline = self._event_scoreline(match, event)
                text = f"⚽ 进球 {event.minute}\n{scoreline}\n{event.team}：{player}{extra}"
            else:
                text = f"🟥 红牌 {event.minute}\n{self._scoreline(match)}\n{event.team}：{event.player or '球员待更新'}"
            self.send(text + self._timestamp())
            self.store.mark_sent(key)

    def _score_correction(self, match: Match, previous: dict) -> None:
        old_total = previous["home_score"] + previous["away_score"]
        new_total = match.home_score + match.away_score
        if new_total < old_total:
            self._once(
                match,
                f"correction:{match.home_score}:{match.away_score}",
                f"⚠️ 比分修正 / 可能为 VAR 取消进球\n{self._scoreline(match)}",
            )
        elif new_total > old_total and not match.events:
            self._once(
                match,
                f"score-change:{match.home_score}:{match.away_score}",
                f"⚽ 比分变化，进球详情待更新\n{self._scoreline(match)}",
            )

    def _once(self, match: Match, suffix: str, text: str) -> None:
        key = f"{match.match_id}:{suffix}"
        if not self.store.was_sent(key):
            self.send(text + self._timestamp())
            self.store.mark_sent(key)

    @staticmethod
    def _event_key(match: Match, fingerprint: str) -> str:
        return f"{match.match_id}:{fingerprint}"

    @staticmethod
    def _event_scoreline(match: Match, event) -> str:
        home_score = event.home_score if event.home_score is not None else match.home_score
        away_score = event.away_score if event.away_score is not None else match.away_score
        return f"{match.home} {home_score}-{away_score} {match.away}"

    @staticmethod
    def _scoreline(match: Match) -> str:
        return f"{match.home} {match.home_score}-{match.away_score} {match.away}"

    def _timestamp(self) -> str:
        now = datetime.now(self.tz).strftime("%H:%M:%S %Z")
        return f"\n推送时间：{now}"

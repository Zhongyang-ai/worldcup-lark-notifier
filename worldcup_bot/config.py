from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    lark_webhook_url: str
    lark_secret: str
    timezone: str
    poll_live_seconds: int
    poll_idle_seconds: int
    request_timeout_seconds: int
    notify_kickoff: bool
    notify_halftime: bool
    notify_red_card: bool
    send_existing_on_start: bool
    heartbeat_hour: int
    schedule_preview_hour: int
    deepseek_api_key: str
    deepseek_model: str
    deepseek_timeout_seconds: int
    deepseek_reasoning_effort: str
    prediction_enabled: bool
    database_path: str
    health_port: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Config":
        webhook = os.getenv("LARK_WEBHOOK_URL", "").strip()
        if not webhook or "REPLACE_ME" in webhook:
            raise ValueError("LARK_WEBHOOK_URL is required")
        return cls(
            lark_webhook_url=webhook,
            lark_secret=os.getenv("LARK_SECRET", "").strip(),
            timezone=os.getenv("TIMEZONE", "Asia/Singapore"),
            poll_live_seconds=max(5, int(os.getenv("POLL_LIVE_SECONDS", "8"))),
            poll_idle_seconds=max(30, int(os.getenv("POLL_IDLE_SECONDS", "60"))),
            request_timeout_seconds=max(3, int(os.getenv("REQUEST_TIMEOUT_SECONDS", "12"))),
            notify_kickoff=_bool("NOTIFY_KICKOFF", True),
            notify_halftime=_bool("NOTIFY_HALFTIME", True),
            notify_red_card=_bool("NOTIFY_RED_CARD", True),
            send_existing_on_start=_bool("SEND_EXISTING_ON_START", False),
            heartbeat_hour=int(os.getenv("HEARTBEAT_HOUR", "9")) % 24,
            schedule_preview_hour=int(os.getenv("SCHEDULE_PREVIEW_HOUR", "22")) % 24,
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
            deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro").strip(),
            deepseek_timeout_seconds=max(20, int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "300"))),
            deepseek_reasoning_effort=os.getenv("DEEPSEEK_REASONING_EFFORT", "high").strip(),
            prediction_enabled=_bool("PREDICTION_ENABLED", True),
            database_path=os.getenv("DATABASE_PATH", "data/worldcup.db"),
            health_port=int(os.getenv("HEALTH_PORT", "8080")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

from __future__ import annotations

import json
import logging
import signal
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

from .config import Config
from .engine import EventEngine
from .lark import LarkNotifier
from .provider import EspnProvider
from .prediction import DeepSeekPredictor
from .store import Store

LOG = logging.getLogger("worldcup_bot")


class Health:
    last_success = "never"
    last_error = ""


def _start_health_server(port: int) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ("/", "/health"):
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps({"status": "ok", "last_success": Health.last_success, "last_error": Health.last_error}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()


def main() -> None:
    config = Config.from_env()
    logging.basicConfig(level=config.log_level, format="%(asctime)s %(levelname)s %(message)s")
    provider = EspnProvider(config.request_timeout_seconds)
    store = Store(config.database_path)
    notifier = LarkNotifier(config.lark_webhook_url, config.lark_secret, config.request_timeout_seconds)
    engine = EventEngine(config, store, notifier.send)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    _start_health_server(config.health_port)
    threading.Thread(target=_schedule_worker, args=(config, stop), daemon=True).start()
    LOG.info("World Cup notifier started")

    while not stop.is_set():
        live = False
        try:
            matches = provider.fetch_matches()
            live = any(match.is_live for match in matches)
            for match in matches:
                engine.process(match)
            Health.last_success = datetime.now().astimezone().isoformat()
            Health.last_error = ""
            _daily_heartbeat(config, store, notifier, matches)
            LOG.info("Processed %d matches; live=%s", len(matches), live)
        except Exception as exc:
            Health.last_error = str(exc)
            LOG.exception("Polling cycle failed")
        stop.wait(config.poll_live_seconds if live else config.poll_idle_seconds)


def _schedule_worker(config: Config, stop: threading.Event) -> None:
    provider = EspnProvider(config.request_timeout_seconds)
    store = Store(config.database_path)
    notifier = LarkNotifier(config.lark_webhook_url, config.lark_secret, config.request_timeout_seconds)
    predictor = DeepSeekPredictor(config.deepseek_api_key, config.deepseek_model)
    tz = ZoneInfo(config.timezone)

    while not stop.is_set():
        now = datetime.now(tz)
        tomorrow = now.date() + timedelta(days=1)
        key = f"schedule-preview:{tomorrow.isoformat()}"
        if now.hour == config.schedule_preview_hour and not store.get_meta(key):
            try:
                LOG.info("Starting schedule preview for %s", tomorrow)
                matches = provider.fetch_matches()
                _daily_schedule_preview(
                    config,
                    store,
                    notifier,
                    matches,
                    now=now,
                    provider=provider,
                    predictor=predictor,
                )
                if store.get_meta(key):
                    LOG.info("Schedule preview sent for %s", tomorrow)
            except Exception:
                LOG.exception("Schedule preview worker failed for %s", tomorrow)
        stop.wait(15 if now.hour == config.schedule_preview_hour else 60)


def _daily_heartbeat(config: Config, store: Store, notifier: LarkNotifier, matches) -> None:
    now = datetime.now(ZoneInfo(config.timezone))
    key = f"heartbeat:{now.date().isoformat()}"
    if now.hour != config.heartbeat_hour or store.get_meta(key):
        return
    upcoming = [m for m in matches if m.state == "pre"]
    notifier.send(f"✅ 世界杯推送服务运行正常\n当前抓取到 {len(upcoming)} 场待赛比赛\n时间：{now:%Y-%m-%d %H:%M %Z}")
    store.set_meta(key, "sent")


def _daily_schedule_preview(
    config: Config,
    store: Store,
    notifier: LarkNotifier,
    matches,
    now: datetime | None = None,
    provider: EspnProvider | None = None,
    predictor: DeepSeekPredictor | None = None,
) -> None:
    tz = ZoneInfo(config.timezone)
    now = now.astimezone(tz) if now else datetime.now(tz)
    tomorrow = now.date() + timedelta(days=1)
    key = f"schedule-preview:{tomorrow.isoformat()}"
    if now.hour != config.schedule_preview_hour or store.get_meta(key):
        return

    fixtures = []
    for match in matches:
        if not match.start_time:
            continue
        kickoff = datetime.fromisoformat(match.start_time.replace("Z", "+00:00"))
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        local_kickoff = kickoff.astimezone(tz)
        if local_kickoff.date() == tomorrow:
            fixtures.append((local_kickoff, match))

    fixtures.sort(key=lambda item: item[0])
    title = f"📅 明日世界杯赛程 | {tomorrow:%Y-%m-%d}（新加坡时间）"
    if fixtures:
        lines = [title]
        for kickoff, match in fixtures:
            lines.append(f"{kickoff:%H:%M}  {match.home} vs {match.away}")
        lines.append(f"\n共 {len(fixtures)} 场")
        message = "\n".join(lines)
    else:
        message = f"{title}\n明日无比赛"

    if config.prediction_enabled and predictor and predictor.enabled and provider and fixtures:
        try:
            contexts = [provider.fetch_prediction_context(match) for _, match in fixtures]
            analysis, usage = predictor.predict(contexts)
            if analysis:
                message += "\n\n" + analysis
            LOG.info("DeepSeek prediction usage: %s", usage)
        except Exception:
            LOG.exception("AI prediction failed; sending schedule without analysis")
            message += "\n\n⚠️ 本次 AI 分析暂不可用，赛程推送不受影响。"

    notifier.send(message)
    store.set_meta(key, "sent")

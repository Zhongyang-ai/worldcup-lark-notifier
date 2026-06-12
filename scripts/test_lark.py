#!/usr/bin/env python3
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


def load_env(path: str = ".env") -> None:
    for line in (PROJECT_ROOT / path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


load_env()
from worldcup_bot.config import Config
from worldcup_bot.lark import LarkNotifier

cfg = Config.from_env()
LarkNotifier(cfg.lark_webhook_url, cfg.lark_secret).send("✅ 世界杯实时推送机器人连接成功")
print("Lark test message sent")

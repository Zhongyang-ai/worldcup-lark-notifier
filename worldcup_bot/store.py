from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone

from .models import Match


class Store:
    def __init__(self, path: str):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS match_state (match_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS sent_event (fingerprint TEXT PRIMARY KEY, sent_at TEXT NOT NULL)"
        )
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        self.db.commit()

    def get_match(self, match_id: str) -> dict | None:
        row = self.db.execute("SELECT payload FROM match_state WHERE match_id = ?", (match_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save_match(self, match: Match) -> None:
        payload = json.dumps(
            {
                "home_score": match.home_score,
                "away_score": match.away_score,
                "state": match.state,
                "status_name": match.status_name,
            }
        )
        self.db.execute(
            "INSERT INTO match_state VALUES (?, ?, ?) ON CONFLICT(match_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at",
            (match.match_id, payload, datetime.now(timezone.utc).isoformat()),
        )
        self.db.commit()

    def was_sent(self, fingerprint: str) -> bool:
        return self.db.execute("SELECT 1 FROM sent_event WHERE fingerprint = ?", (fingerprint,)).fetchone() is not None

    def mark_sent(self, fingerprint: str) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO sent_event VALUES (?, ?)",
            (fingerprint, datetime.now(timezone.utc).isoformat()),
        )
        self.db.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self.db.execute(
            "INSERT INTO metadata VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value)
        )
        self.db.commit()


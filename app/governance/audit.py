"""Audit logging — SPLIT 6 owns this file.
Writes one JSON line per handled request to logs/audit.log.
No message content or sensitive data is stored, only execution metadata.
"""
from __future__ import annotations
import json
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIR / "audit.log"


def record_event(user: str, skill: str, status: str, duration: float) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "user": user,
        "skill": skill,
        "status": status,
        "duration_s": round(duration, 3),
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

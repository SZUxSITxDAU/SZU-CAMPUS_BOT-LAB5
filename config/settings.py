"""Shared config — SPLIT 6 owns this file."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
KNOWLEDGE_DIR = ROOT / "knowledge"
LOG_DIR = ROOT / "logs"

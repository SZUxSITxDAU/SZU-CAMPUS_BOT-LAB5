"""CampusBot launch entry point — required by CampusBot Launcher.app.
SPLIT 1 owns this file. Keep it a thin bootstrap that starts app.api.server:app.
Do not rename or move this file — the launcher always runs project/main.py.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402
from app.api.server import app  # noqa: E402

if __name__ == "__main__":
    host = os.getenv("CAMPUSBOT_HOST", "127.0.0.1")
    port = int(os.getenv("CAMPUSBOT_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

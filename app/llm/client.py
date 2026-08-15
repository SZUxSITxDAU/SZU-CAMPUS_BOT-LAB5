"""LLM client — SPLIT 6 owns this file.
Wraps the local Ollama API so no other module talks to Ollama directly.

The launcher assigns Ollama a DYNAMIC port from 127.0.0.1:11435-11445
(see the lab PDF), and Ollama takes a few seconds after "Listening" to
finish loading the model before /api/tags returns a clean 200 (it can
return 500 briefly during startup). This client retries with a time
budget instead of failing on the first check, so an early message right
after launch doesn't get spuriously rejected. Set OLLAMA_URL explicitly
to skip discovery entirely.
"""
from __future__ import annotations
import os
import time
import httpx

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
CANDIDATE_PORTS = [11434] + list(range(11435, 11446))
DISCOVERY_TIMEOUT_S = 45.0
DISCOVERY_POLL_INTERVAL_S = 1.5
_cached_base_url: str | None = None


def _probe_ports() -> "str | None":
    for port in CANDIDATE_PORTS:
        base = f"http://127.0.0.1:{port}"
        try:
            response = httpx.get(f"{base}/api/tags", timeout=1.0)
            if response.status_code == 200:
                return base
        except httpx.HTTPError:
            continue
    return None


def _discover_ollama_base() -> str:
    global _cached_base_url
    if _cached_base_url:
        return _cached_base_url

    env_url = os.getenv("OLLAMA_URL")
    if env_url:
        _cached_base_url = env_url.removesuffix("/api/chat")
        return _cached_base_url

    deadline = time.monotonic() + DISCOVERY_TIMEOUT_S
    while time.monotonic() < deadline:
        found = _probe_ports()
        if found:
            _cached_base_url = found
            return found
        time.sleep(DISCOVERY_POLL_INTERVAL_S)

    raise RuntimeError(
        f"Could not find a ready Ollama instance within {DISCOVERY_TIMEOUT_S:.0f}s. "
        "Confirm CampusBot Launcher.app has fully started before sending a message."
    )


class LLMClient:
    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        base = _discover_ollama_base()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.0, "num_ctx": 4096, "seed": 42},
        }
        response = httpx.post(f"{base}/api/chat", json=payload, timeout=90)
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "").strip()

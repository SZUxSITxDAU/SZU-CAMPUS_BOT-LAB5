# CampusBot — Modular Agent Harness (Team 8)

Lab 5 "Engineering a Reliable AI Agent Product" — SZU International Summer Camp 2026.
The provided single-file CampusBot prototype, refactored into a governed, testable
agent runtime: Skills, Runtime orchestration, Governance, and automated validation.

## Architecture

```
Browser (web/, role selector)
  |  POST /chat {user, role, message, session_id}
  v
FastAPI            app/api/server.py       structured response contract (Bonus 1)
  v
Orchestrator       app/runtime/orchestrator.py
  |-- 1. Guardrail     governance/guardrail.py    -> blocked
  |-- 2. Skill Router  runtime/router.py          -> unmatched
  |-- 3. Permissions   governance/permissions.py  -> forbidden (Bonus 2)
  |-- 4. Selected Skill
  |       campus | course | library    knowledge/*.json + LLM
  |       translation | summary        LLM only
  |       composed_briefing            knowledge -> summary -> translation (Bonus 3)
  |-- 5. LLM Client    app/llm/client.py          local Ollama (qwen3:0.6b)
  v
Audit              governance/audit.py -> logs/audit.log (one JSON line per request)
```

Every outcome — success, unavailable, unmatched, blocked, forbidden, error — is
audited and returned as a structured status. Short-term conversation memory
(`app/runtime/memory.py`) is kept per browser session so follow-up messages like
"translate to chinese" work against the previous answer.

## Roles

| Role   | Skills                                                        |
|--------|---------------------------------------------------------------|
| guest  | campus                                                        |
| member | campus, course, library, translation                          |
| admin  | all, including summary and composed_briefing                  |

A composed request is authorised against the Skills it actually invokes, so a
member may ask a knowledge question and have the answer translated, but may not
summarise.

## Running

With the offline lab package: copy this repository's contents into the package's
`CampusBot/` folder and double-click `Start CampusBot.cmd`. The launcher starts
Ollama, loads `qwen3:0.6b`, runs `main.py`, and opens http://127.0.0.1:8000/.

Manually (requires a local Ollama with `qwen3:0.6b`):

```
python main.py
```

`OLLAMA_URL` / `OLLAMA_MODEL` override discovery; otherwise ports 11434–11445
are probed automatically.

## Tests

43 tests, no Ollama required (deterministic fakes in `tests/fakes.py`):

```
python -m unittest discover -s tests -p "test_*.py" -v
```

or double-click `Run Tests.cmd` in the lab package.

The original single-file starter is preserved in git history (commit `d88d2e9`).

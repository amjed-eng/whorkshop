# Intruder Invisible — Engineering Log

## Architecture Invariants

- Flask must never wait for Groq.
- SQLite evidence is persisted before cloud AI analysis.
- One normalized event model feeds DB, state, UI/SSE and AI.
- Groq runs only in a background worker.
- Telegram transport is asynchronous and not implemented before its dedicated commit.
- SQLite connections are never shared across threads.
- Reset increments generation.
- Stale AI results from an older generation must be discarded.
- SSE clients receive a current state snapshot when they connect.
- No frontend framework or extra infrastructure is allowed.

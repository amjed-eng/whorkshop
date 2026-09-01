# INTRUDER INVISIBLE — المتسلل الخفي

**Real-time Cybersecurity Alert Processing & Incident Visualization Demo**  
Flask · SQLite · Server-Sent Events (SSE) · Groq AI · Telegram Bot API · Apache ECharts · Web Audio API · OpenCanary-oriented ingestion · Replay Mode

---

## 1. Overview

**INTRUDER INVISIBLE** is a compact cybersecurity incident-processing and visualization system designed to demonstrate how a security event can move through a complete response pipeline:

```text
Security Event / OpenCanary-oriented Input
                ↓
          Flask Ingestion
                ↓
      Strict Event Normalization
                ↓
        SQLite Evidence Store
                ↓
       Local Detection & State
                ↓
      Immediate SSE Dashboard
                ↓
        Async Groq AI Worker
                ↓
   AI Result → Dashboard / SQLite
                ↓
   CRITICAL only → Telegram Queue
                ↓
        Telegram Bot API
```

The system deliberately keeps the critical path small. A security event is persisted and reflected on the dashboard **before** waiting for Groq or Telegram.

The project currently provides:

- strict canonical event validation;
- SQLite evidence persistence;
- local risk/state detection independent from cloud AI;
- basic per-source behavioural correlation;
- recognition of reconnaissance such as Nmap/port scanning;
- asynchronous Groq analysis;
- asynchronous CRITICAL Telegram alerts;
- real-time browser updates through SSE;
- a local Apache ECharts cyber-operations dashboard;
- Web Audio critical alerts after explicit user interaction;
- replay mode using the exact same ingestion pipeline as live events;
- Crime Scene reconstruction from SQLite;
- Executive presentation mode;
- six-system Preflight checks;
- automated stability/regression tests.

> **Important:** the current application is a hardened workshop/security-demo platform and a strong engineering prototype. It must **not** be described as a full production SIEM yet. See [Known Production Gaps](#20-known-production-gaps).

---

## 2. Design Goals

The project follows four core principles:

1. **Evidence first** — an accepted event is written to SQLite before cloud AI processing.
2. **Immediate local response** — the dashboard and risk state do not wait for Groq.
3. **Failure isolation** — Groq or Telegram failure must not stop ingestion, local risk, evidence persistence, or the dashboard.
4. **Minimal architecture** — no Redis, Celery, Kafka, React, Node.js, WebSockets, external chart CDN, or frontend framework is required.

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python + Flask |
| Evidence Store | SQLite (`sqlite3`) |
| Live Browser Updates | Server-Sent Events (`EventSource`) |
| AI Analysis | Groq Python SDK |
| AI Model | `openai/gpt-oss-20b` |
| Alert Transport | Telegram Bot API over HTTPS |
| Visualization | Apache ECharts, local `static/echarts.min.js` |
| Frontend | HTML + CSS + Vanilla JavaScript |
| Audio | Native Web Audio API |
| Queues | `queue.Queue` |
| Concurrency | `threading` |
| Tests | Python `unittest` |

### Intentionally not used

- React / Vue / Angular
- Node.js
- Bootstrap / Tailwind / Material UI
- Redis / Celery / Kafka
- WebSocket / Socket.IO
- Elasticsearch / Grafana
- Docker Compose as an architectural dependency
- external JavaScript/CDN assets
- `python-telegram-bot` / Telethon

---

## 4. Current Architecture

```text
                         ┌─────────────────────┐
                         │   Event Producer    │
                         │ OpenCanary / Replay │
                         └──────────┬──────────┘
                                    │
                                    ▼
                    POST /webhook/opencanary
                         or /demo/replay/N
                                    │
                                    ▼
                         ┌─────────────────┐
                         │ normalize_event │
                         └────────┬────────┘
                                  │
                                  ▼
                     ┌─────────────────────┐
                     │ SQLite Evidence DB  │
                     └──────────┬──────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │ Local State/Risk │
                       │    state.py      │
                       └───────┬──────────┘
                               │
                     ┌─────────┴──────────┐
                     ▼                    ▼
               SSE EVENT/STATE        AI Queue
                     │                    │
                     ▼                    ▼
             Browser Dashboard      Groq AI Worker
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
                      SQLite AI Result          SSE AI_RESULT
                              │
                              ▼
                    CRITICAL + alert only
                              │
                              ▼
                        Telegram Queue
                              │
                              ▼
                      Telegram Bot API
```

### Architecture invariants

- Flask ingestion never waits for Groq.
- Flask ingestion never sends Telegram synchronously.
- SQLite evidence is saved before AI analysis.
- SQLite connections are short-lived and not shared across threads.
- Live and Replay both call the same `ingest_event()` function.
- Browser/SSE receives normalized event data, not raw OpenCanary payloads.
- Reset increments a generation counter.
- Stale AI/Telegram work from an older generation is ignored.
- ECharts is served locally.
- Dynamic frontend data is not rendered with `innerHTML`.
- Flask production demo startup uses `debug=False` and `use_reloader=False`.

---

## 5. Project Structure

```text
intruder-invisible/
├── app.py
├── state.py
├── db.py
├── ai_worker.py
├── telegram_worker.py
├── preflight.py
├── replay.py
├── prompt.py
├── requirements.txt
├── ENGINEERING_LOG.md
├── PHASE_2_EXECUTION_PLAN.md
├── PHASE_3_TASK.md
├── architecture.txt
├── data/
│   └── evidence.sqlite3              # generated runtime evidence DB
├── replay/
│   └── events.json
├── templates/
│   └── index.html
├── static/
│   ├── app.js
│   ├── style.css
│   └── echarts.min.js
└── tests/
    ├── test_ai_worker.py
    ├── test_app.py
    ├── test_audio.py
    ├── test_db.py
    ├── test_echarts.py
    ├── test_preflight.py
    ├── test_replay.py
    ├── test_stability.py
    ├── test_state.py
    ├── test_state_detection.py
    ├── test_telegram_worker.py
    ├── test_timeline.py
    └── test_ui.py
```

---

## 6. Requirements

### Recommended environment

- Linux recommended for the workshop environment
- Python **3.12** recommended for compatibility with the currently used Groq/Pydantic native dependencies
- `pip`
- network access if using real Groq or Telegram
- OpenCanary only when testing true live honeypot ingestion

### Python dependencies

The project's `requirements.txt` contains:

```text
Flask
groq
```

The remaining backend functionality uses the Python Standard Library.

---

## 7. Installation

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify the real dependencies:

```bash
python -c "import flask, groq; print('Flask:', flask.__file__); print('Groq:', groq.__file__)"
```

---

## 8. Environment Variables

### Groq

```bash
export GROQ_API_KEY='your-groq-api-key'
```

### Telegram

```bash
export TELEGRAM_BOT_TOKEN='your-bot-token'
export TELEGRAM_CHAT_ID='your-chat-id'
```

### Preflight Flask URL

Optional. Defaults to `http://127.0.0.1:5000`:

```bash
export PREFLIGHT_FLASK_URL='http://127.0.0.1:5000'
```

### OpenCanary Preflight URL

The current preflight implementation expects:

```bash
export OPEN_CANARY_WEBHOOK_URL='http://<opencanary-host>:<port>/<reachable-path>'
```

`check_opencanary()` performs a real HTTP `HEAD` request to this URL.

> This variable is a **reachability check**, not a native OpenCanary event adapter.

---

## 9. Starting the Application

Activate the environment:

```bash
source .venv/bin/activate
```

Start Flask:

```bash
python app.py
```

Default local URL:

```text
http://127.0.0.1:5000
```

Open the dashboard in a browser:

```text
http://127.0.0.1:5000/
```

Check health from another terminal:

```bash
curl http://127.0.0.1:5000/health
```

Expected healthy response:

```json
{
  "db": "connected",
  "status": "healthy"
}
```

---

## 10. Canonical Security Event Contract

`POST /webhook/opencanary` currently expects the project's **canonical normalized event shape**:

```json
{
  "event_type": "Port Scan",
  "source": "192.168.1.50",
  "target_service": "Web Service",
  "timestamp": "2026-09-01T03:00:00Z",
  "attempt_count": 25,
  "previous_related_events": [],
  "current_risk_context": {
    "risk_score": 0,
    "stage": "Discovery"
  }
}
```

### Validation rules

- `event_type`: non-empty string
- `source`: non-empty string
- `target_service`: non-empty string
- `timestamp`: non-empty string
- `attempt_count`: integer >= 1
- `previous_related_events`: list
- `current_risk_context`: object
- `current_risk_context.risk_score`: integer 0–100
- `current_risk_context.stage`: string

An invalid payload returns HTTP `400`.

### Important OpenCanary note

The route name is `/webhook/opencanary`, but the current implementation validates the **canonical project schema** above. A production-quality adapter that converts every native OpenCanary log format into this schema remains a separate productization task.

Therefore:

```text
Native OpenCanary payload
        ↓
[adapter/mapping still requires production hardening]
        ↓
Canonical event above
        ↓
INTRUDER INVISIBLE
```

Do not assume an arbitrary native OpenCanary JSON packet will be accepted until its fields are mapped into this contract.

---

## 11. Local Detection, Correlation & Risk Model

The system reacts locally before Groq returns.

### Core presentation states

```text
NORMAL
  ↓
UNDER_OBSERVATION
  ↓
CRITICAL_INTRUSION
  ↓
CONTAINED
  ↓
FORENSIC
  ↓
EXECUTIVE
```

### Risk behaviour

Typical workshop progression:

| Scenario | Risk | State |
|---|---:|---|
| First low-signal event from a source | 21 | `UNDER_OBSERVATION` |
| Repeated/suspicious/recon activity | 48 | `UNDER_OBSERVATION` |
| High-impact or sensitive event | 91 | `CRITICAL_INTRUSION` |

Risk is intentionally presentation-oriented and deterministic. It is not intended as a universal CVSS/SIEM risk engine.

### Reconnaissance detection

The hardened state logic recognizes signals including:

- port scan
- Nmap
- SYN scan
- network scan
- port sweep
- service discovery
- reconnaissance
- enumeration
- banner grabbing
- probing

A reconnaissance event can move directly to observation/risk 48 even when it is the first event from that source.

### Authentication attack signals

Examples:

- brute force
- password spray
- credential stuffing
- repeated authentication/login failures

### Exploit-attempt signals

Examples:

- exploit attempt
- SQL injection
- command injection
- path traversal
- directory traversal
- file inclusion

### High-impact signals

Examples that can justify a critical transition include:

- privilege escalation
- remote code execution
- command execution
- reverse shell
- credential dumping
- exfiltration
- ransomware
- malware execution
- lateral movement
- persistence
- account takeover
- successful exploit

### Sensitive assets

The state engine treats protected assets such as the following as critical targets:

- Admin System
- Digital Vault
- management plane/console
- domain controller
- secrets vault
- privileged access systems

### Behavioural fallback

The engine also considers:

- `attempt_count`
- number of `previous_related_events`
- upstream `current_risk_context`
- per-source activity history

This provides limited detection for unknown/vendor-specific labels without depending only on exact strings.

### Risk monotonicity while critical

Once the system is in `CRITICAL_INTRUSION`, a later benign/new-source event cannot silently reduce the active risk to 21 or 48.

---

## 12. SQLite Evidence Store

Database path:

```text
data/evidence.sqlite3
```

The evidence table records:

- timestamp
- source
- service
- event type
- SHA-256 hash of the received raw event object
- AI classification JSON
- risk

The raw payload itself is **not persisted** in SQLite.

Each DB operation creates its own SQLite connection and closes it after use.

### Evidence order

Events are read using:

```text
ORDER BY timestamp ASC, rowid ASC
```

### Reset

`POST /demo/reset` removes demo evidence rows but retains the database file/schema.

---

## 13. Server-Sent Events (SSE)

Browser stream:

```text
GET /events
```

The browser uses:

```javascript
new EventSource('/events')
```

### SSE envelope

```json
{
  "kind": "EVENT",
  "payload": {}
}
```

Supported application messages include:

- `EVENT`
- `STATE`
- `AI_RESULT`
- `RESET`

A new SSE connection receives the current `STATE` snapshot immediately.

An idle connection receives heartbeat comments approximately every 15 seconds and remains open.

### Current state snapshot

The hardened state snapshot includes:

- `current_state`
- `current_risk`
- `current_stage`
- `current_source`
- `timeline`
- `generation`
- `ai_result`
- `event_count`
- `most_targeted_asset`

---

## 14. Groq AI Worker

Groq processing happens in a dedicated background worker.

Model:

```text
openai/gpt-oss-20b
```

The workflow is:

```text
AI queue
  ↓
Generation check
  ↓
Groq structured-output request
  ↓
Strict local validation
  ↓
Generation check again
  ↓
SQLite update
  ↓
Local state apply
  ↓
SSE AI_RESULT
  ↓
CRITICAL + non-empty telegram_alert → Telegram queue
```

### AI output contract

The AI result contains 15 required fields:

1. `event_type`
2. `source`
3. `target_service`
4. `timestamp`
5. `attempt_count`
6. `previous_related_events`
7. `current_risk_context`
8. `severity`
9. `risk_score`
10. `stage`
11. `executive_title`
12. `executive_summary`
13. `business_impact`
14. `recommended_action`
15. `telegram_alert`

Invalid structured output is discarded. Existing SQLite evidence and local dashboard state remain available.

### Generation protection

If a demo reset occurs while Groq is still processing, the old result is rejected before it can pollute the new round.

---

## 15. Telegram Alerts

Telegram uses the Bot API directly with the Python Standard Library.

Flow:

```text
Validated AI result
  ↓
severity == CRITICAL
AND telegram_alert is non-empty
  ↓
telegram_queue
  ↓
Telegram worker
  ↓
Telegram Bot API
```

Required environment variables:

```bash
export TELEGRAM_BOT_TOKEN='...'
export TELEGRAM_CHAT_ID='...'
```

The browser never receives Telegram credentials.

Telegram network/API failure is isolated from Flask ingestion and dashboard state.

---

## 16. Dashboard & Visualization

The frontend is a local cyber-operations interface implemented with:

- `templates/index.html`
- `static/style.css`
- `static/app.js`
- `static/echarts.min.js`

### Visual components

- risk gauge
- logical Digital City network graph
- dynamic external-source attack path
- timeline
- current state
- event count
- most-targeted asset
- AI incident brief
- controls for Replay, Containment, Crime Scene, Executive mode, Reset and Audio

### Logical Digital City

Core nodes:

```text
Internet
  ↓
Gateway
  ↓
Web Service
  ↓
File Service
  ↓
Admin System
  ↓
Digital Vault
```

Common real service names are mapped to logical city assets where appropriate; unknown services can be represented as dynamic target nodes.

### Timeline

Stages:

```text
Discovery
→ Service Probe
→ Access Attempt
→ Escalation
→ Containment
```

### Frontend security constraints

- no CDN
- no Bootstrap/Tailwind
- no external web fonts
- no `innerHTML`
- no `outerHTML`
- no `insertAdjacentHTML`
- API secrets never appear in frontend code

---

## 17. Web Audio

Critical audio uses the native Web Audio API rather than an external sound file.

The browser requires explicit user interaction through the **ARM AUDIO** control before sound is enabled.

If the browser blocks or cannot initialize audio, the visual response continues normally.

Critical audio is deduplicated per demo generation.

---

## 18. Replay Mode

Replay is the safe workshop fallback when Live/OpenCanary mode is unavailable.

Replay data:

```text
replay/events.json
```

Available routes:

```text
POST /demo/replay/1
POST /demo/replay/2
POST /demo/replay/3
```

All Replay events call the exact same:

```python
ingest_event(raw_event)
```

used by the live webhook.

### Prepared scenario

```text
Event 1
Login Attempt
10.0.0.99 → Web Service
Risk 21

Event 2
Port Scan
10.0.0.99 → Web Service
Risk 48

Event 3
Privilege Escalation
10.0.0.99 → Admin System
Risk 91
CRITICAL_INTRUSION
```

### Run the full Replay sequence

Reset first:

```bash
curl -X POST http://127.0.0.1:5000/demo/reset
```

Then:

```bash
curl -X POST http://127.0.0.1:5000/demo/replay/1
curl -X POST http://127.0.0.1:5000/demo/replay/2
curl -X POST http://127.0.0.1:5000/demo/replay/3
```

Contain:

```bash
curl -X POST http://127.0.0.1:5000/contain
```

Crime Scene:

```bash
curl -X POST http://127.0.0.1:5000/crime-scene
```

Executive mode:

```bash
curl -X POST http://127.0.0.1:5000/executive
```

Reset again:

```bash
curl -X POST http://127.0.0.1:5000/demo/reset
```

---

## 19. API Reference

| Method | Route | Purpose |
|---|---|---|
| GET | `/` | Dashboard |
| GET | `/health` | Flask/SQLite health |
| POST | `/webhook/opencanary` | Canonical security-event ingestion |
| GET | `/events` | SSE state/event stream |
| POST | `/demo/replay/<event_number>` | Replay prepared event |
| POST | `/demo/reset` | Reset presentation, DB evidence and Telegram dedup |
| POST | `/contain` | Move state to containment |
| POST | `/crime-scene` | Build forensic evidence view from SQLite |
| POST | `/executive` | Enter executive presentation mode |

### Observe SSE from terminal

```bash
curl -N http://127.0.0.1:5000/events
```

Keep that terminal open and trigger an event from another terminal.

---

## 20. Testing Detection from the Terminal

### A. Recommended first test: direct canonical Port Scan event

Start Flask, then execute:

```bash
curl -X POST http://127.0.0.1:5000/webhook/opencanary \
  -H 'Content-Type: application/json' \
  -d '{
    "event_type": "Port Scan",
    "source": "192.168.1.99",
    "target_service": "Web Service",
    "timestamp": "2026-09-01T03:00:00Z",
    "attempt_count": 30,
    "previous_related_events": [],
    "current_risk_context": {
      "risk_score": 0,
      "stage": "Discovery"
    }
  }'
```

Expected local behaviour:

```text
UNDER_OBSERVATION
risk approximately 48
stage Service Probe
```

### B. Critical event example

```bash
curl -X POST http://127.0.0.1:5000/webhook/opencanary \
  -H 'Content-Type: application/json' \
  -d '{
    "event_type": "Privilege Escalation",
    "source": "192.168.1.99",
    "target_service": "Admin System",
    "timestamp": "2026-09-01T03:01:00Z",
    "attempt_count": 5,
    "previous_related_events": ["Port Scan"],
    "current_risk_context": {
      "risk_score": 48,
      "stage": "Access Attempt"
    }
  }'
```

Expected local behaviour:

```text
CRITICAL_INTRUSION
risk >= 91
stage Escalation
```

### C. Real Nmap testing

Nmap must scan a host/service actually monitored by OpenCanary. It does **not** automatically generate a Flask canonical event merely because Flask is running.

Set the honeypot target first:

```bash
export HONEYPOT_IP='192.168.1.50'
```

Verify it is not empty:

```bash
echo "$HONEYPOT_IP"
```

Then, inside an authorized lab only:

```bash
nmap -Pn --top-ports 100 "$HONEYPOT_IP"
```

or:

```bash
nmap -Pn -sV -p 22,80,445,3389 "$HONEYPOT_IP"
```

If Nmap runs but the dashboard does not react:

1. verify OpenCanary itself observed the scan;
2. inspect the OpenCanary event payload;
3. verify it is being mapped to the canonical schema documented above;
4. verify the mapped event reaches `/webhook/opencanary`.

The current repository does **not** claim universal native OpenCanary payload adaptation.

Only perform scanning against systems you own or are explicitly authorized to test.

---

## 21. Crime Scene / Forensics

`POST /crime-scene` reads SQLite evidence and reconstructs exactly these concepts:

1. First Seen
2. Origin
3. First Target
4. Activity Sequence
5. Critical Transition

The project intentionally uses the phrase **Origin Observed First** rather than claiming a definitive “Patient Zero.”

Forensic reconstruction uses persisted SQLite evidence, not a hard-coded browser animation.

---

## 22. Reset & Generation Safety

Reset endpoint:

```bash
curl -X POST http://127.0.0.1:5000/demo/reset
```

Reset performs the following:

- increments the generation counter;
- returns state to `NORMAL`;
- risk becomes `0`;
- clears timeline;
- clears AI presentation result;
- clears source/target correlation metrics;
- removes current demo evidence from SQLite;
- clears Telegram deduplication;
- broadcasts `RESET` to SSE clients.

Old AI and Telegram work carrying a previous generation is discarded.

---

## 23. Preflight 6/6

Run Flask first, then in another terminal:

```bash
python preflight.py
```

Preflight checks:

1. OpenCanary reachable
2. Flask healthy
3. Groq responding
4. Telegram test delivered
5. SQLite writable
6. ECharts available locally through Flask

Success is printed only when all six pass:

```text
DEMO READY — 6/6 SYSTEMS ONLINE
```

Example degraded output may be:

```text
DEMO NOT READY — 3/6 SYSTEMS ONLINE
LIVE MODE UNAVAILABLE — USE REPLAY
```

### Important behaviour

- OpenCanary failure means Live mode is unavailable; Replay can still be used.
- SQLite failure is a blocking demo-readiness failure.
- A missing Groq key or Telegram credentials is reported honestly as FAIL.
- Preflight is not executed on every webhook; it is a separate operator command.

---

## 24. Automated Tests

Run the complete suite:

```bash
python -m unittest discover -s tests -v
```

Compile check:

```bash
python -m compileall \
  app.py db.py state.py ai_worker.py telegram_worker.py \
  prompt.py replay.py preflight.py tests
```

### Current reviewed test coverage

The current reviewed source contains **132 tests**: the project's previous 127-test suite plus five additional state/detection regression tests.

The holistic-review regression run completed:

```text
Ran 132 tests
OK
```

The five added regression tests cover:

- first-event Nmap/SYN scan recognition;
- high-volume unknown/vendor event handling;
- correlated high-volume escalation;
- preventing a benign new source from lowering CRITICAL risk;
- truthful `event_count` and `most_targeted_asset` snapshot metrics.

### Environment caveat

During the review environment, the bundled Groq/Pydantic native dependency was built for Python 3.12 while the audit runtime was Python 3.13. An **external temporary import shim** was used only to allow unit tests that already mock/inject the Groq boundary to execute. No shim or fake Groq implementation was added to the project source.

Therefore, before a real deployment/demo, run the complete suite again in the project's intended Python environment and verify real Groq import independently.

---

## 25. Stability Guarantees Covered by Tests

The project includes stability tests for:

- normal event ingestion;
- Groq delay/failure isolation;
- Telegram failure isolation during a critical incident;
- browser reload restoring current SSE state;
- Reset while AI is still in flight;
- Replay 21 → 48 → 91 progression;
- forensics reading evidence from SQLite;
- final reset returning the demo to a clean state.

---

## 26. Security Properties Already Implemented

- Groq API key read from environment only.
- Telegram token/chat ID read from environment only.
- Browser does not call Groq directly.
- Browser does not receive Telegram secrets.
- Raw event payload is not broadcast to the browser.
- Raw event payload is not stored in SQLite; only its SHA-256 hash is stored.
- SQLite operations use independent connections.
- AI structured output is locally validated.
- Stale AI results are generation-protected.
- Stale Telegram tasks are generation-protected.
- Frontend has no external CDN dependency.
- Dynamic UI avoids unsafe HTML injection sinks.
- Groq/Telegram failures are outside the synchronous webhook path.

---

## 27. Known Production Gaps

The current project is intentionally compact. Before describing it as a true production alert-processing platform/SIEM, the following require additional engineering.

### 1. Native OpenCanary adapter

A tested translation layer is needed for real OpenCanary native log formats → canonical event schema.

### 2. Webhook authentication

`/webhook/opencanary` currently needs production controls such as:

- shared-secret/HMAC or mutually authenticated transport;
- source allow-list where appropriate;
- replay protection;
- request-size limits;
- rate limiting.

### 3. Control-plane authentication

Routes such as:

- `/demo/reset`
- `/contain`
- `/crime-scene`
- `/executive`
- `/demo/replay/*`

are designed for a controlled workshop environment and require authentication/authorization and CSRF strategy before exposed deployment.

### 4. Queue durability and backpressure

Current in-process `queue.Queue` workers are not durable across process crashes and are not a distributed queue solution. Production deployment needs explicit capacity/backpressure/retry policy.

### 5. Persistent correlation model

Per-source detection correlation currently lives in process memory. It is not a persistent multi-node incident correlation engine.

### 6. Timestamp normalization

The canonical schema validates timestamps as non-empty strings; production use should normalize/validate UTC timestamps and clock-skew policy.

### 7. AI consistency enforcement

AI output schema is validated, but stronger semantic checks should ensure model-returned source/target/timestamp cannot contradict the original evidence.

### 8. Telegram retry semantics

The current dedup strategy prevents duplicate tasks, but a production transport should define retry/backoff and exactly when an alert becomes “sent.”

### 9. Observability

Production operation requires structured application metrics/logging, queue depth visibility, health/readiness separation and alert delivery metrics.

### 10. Evidence retention and backup

SQLite is appropriate for the workshop architecture, but production policy needs retention, archival, backup, recovery and data-integrity procedures.

---

## 28. Troubleshooting

### Nmap says `No targets were specified`

Your shell variable is empty.

Check:

```bash
echo "$HONEYPOT_IP"
```

Set it:

```bash
export HONEYPOT_IP='127.0.0.1'
```

or use the real authorized honeypot IP:

```bash
export HONEYPOT_IP='192.168.1.50'
```

Then:

```bash
nmap -Pn --top-ports 100 "$HONEYPOT_IP"
```

### Replay works but real Nmap does not

This normally means the application pipeline is functioning but the OpenCanary-native-event → canonical-event mapping is missing/misconfigured.

Check OpenCanary independently before changing `state.py`.

### Groq does not produce an AI result

Check:

```bash
echo "$GROQ_API_KEY"
python -c "from groq import Groq; print('Groq import OK')"
```

The local risk/dashboard should continue operating even when Groq is unavailable.

### Telegram does not deliver

Check:

```bash
echo "$TELEGRAM_BOT_TOKEN"
echo "$TELEGRAM_CHAT_ID"
```

Then run:

```bash
python preflight.py
```

Telegram failure should not stop Flask or local critical state.

### ECharts is blank

Verify local file:

```bash
ls -lh static/echarts.min.js
```

With Flask running:

```bash
curl -I http://127.0.0.1:5000/static/echarts.min.js
```

There should be no CDN dependency.

### SSE appears disconnected

Test directly:

```bash
curl -N http://127.0.0.1:5000/events
```

You should receive an initial STATE frame and periodic heartbeat comments while idle.

### Start from a clean demo state

```bash
curl -X POST http://127.0.0.1:5000/demo/reset
```

---

## 29. Recommended Workshop Flow

Before the audience arrives:

```bash
python -m unittest discover -s tests -v
python preflight.py
```

Then open the dashboard and click **ARM AUDIO**.

Recommended fallback-safe presentation:

```text
RESET
  ↓
Replay Event 1 → Risk 21
  ↓
Replay Event 2 → Risk 48
  ↓
Replay Event 3 → Risk 91 / CRITICAL
  ↓
AI Result
  ↓
Telegram Critical Alert (when configured)
  ↓
ISOLATE THREAT
  ↓
Crime Scene
  ↓
Executive Summary
  ↓
RESET
```

If OpenCanary is correctly integrated, the same pipeline can be fed from authorized live honeypot activity instead of Replay.

---

## 30. Documentation Set Recommended for Full Productization

A complete engineering documentation package should ultimately include:

1. **Product & System Overview**
2. **System Architecture & ADR Register**
3. **Event Ingestion & Canonical Schema Specification**
4. **Detection, Correlation & Risk Model Specification**
5. **API & SSE Contract**
6. **Security Architecture & Threat Model**
7. **AI Analysis & Alerting Specification**
8. **Data & Evidence Management Policy**
9. **Deployment & Configuration Guide**
10. **Operations, Preflight & Incident Runbook**
11. **Verification & Test Strategy**
12. **Frontend UX & Presenter Guide**

The highest-priority next technical document is **Event Ingestion & Canonical Schema Specification**, because reliable native OpenCanary mapping is the largest gap between the current hardened prototype and true live ingestion.

---

## 31. Development Status

### Implemented

- SQLite evidence persistence
- local state/risk engine
- behavioural recon/scan detection
- per-source in-memory correlation
- strict canonical normalization
- SSE dashboard
- asynchronous Groq worker
- strict AI structured output
- asynchronous Telegram worker
- generation safety
- local Apache ECharts
- attack graph
- risk gauge
- incident timeline
- Web Audio alert
- Crime Scene reconstruction
- Executive mode
- Replay mode
- six-check Preflight
- stability tests
- cyberpunk dashboard redesign

### Operationally verified in the reviewed source

- automated unit/regression logic
- Replay path
- SQLite persistence/reset
- local ECharts artifact
- SSE state contracts
- worker failure isolation in tests

### Environment-dependent / must be verified on the target host

- real Groq connectivity and credentials
- real Telegram delivery
- real OpenCanary reachability
- native OpenCanary event mapping
- manual browser visual verification
- network/firewall exposure

---

## 32. Responsible Use

This project is intended for:

- authorized cybersecurity workshops;
- controlled honeypot environments;
- defensive detection demonstrations;
- software engineering/security education;
- testing on systems you own or have explicit permission to assess.

Do not scan, probe, attack, or attempt access against third-party systems without explicit authorization.

---

## 33. Quick Start

```bash
# 1. Environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Optional cloud integrations
export GROQ_API_KEY='...'
export TELEGRAM_BOT_TOKEN='...'
export TELEGRAM_CHAT_ID='...'

# 3. Start server
python app.py
```

In another terminal:

```bash
# 4. Health
curl http://127.0.0.1:5000/health

# 5. Reset
curl -X POST http://127.0.0.1:5000/demo/reset

# 6. Safe deterministic demo
curl -X POST http://127.0.0.1:5000/demo/replay/1
curl -X POST http://127.0.0.1:5000/demo/replay/2
curl -X POST http://127.0.0.1:5000/demo/replay/3

# 7. Preflight
python preflight.py

# 8. Full tests
python -m unittest discover -s tests -v
```

Dashboard:

```text
http://127.0.0.1:5000
```

---

## 34. Project Engineering Record

For the detailed evolution, corrective gates and architecture decisions, see:

```text
ENGINEERING_LOG.md
```

Execution/reference plans:

```text
PHASE_2_EXECUTION_PLAN.md
PHASE_3_TASK.md
```

---

**INTRUDER INVISIBLE** demonstrates a deliberate security-engineering principle:

> **The visible incident response should remain fast and understandable, while cloud intelligence and external notification remain asynchronous and failure-isolated.**

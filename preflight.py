import json
import os
import sqlite3
import urllib.request

import db
import telegram_worker

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

GROQ_MODEL = "openai/gpt-oss-20b"
PREFLIGHT_TELEGRAM_MESSAGE = "INTRUDER INVISIBLE — PRE-FLIGHT TEST"


def flask_base_url():
    return os.environ.get("PREFLIGHT_FLASK_URL", "http://127.0.0.1:5000")


def check_opencanary():
    url = os.environ.get("OPEN_CANARY_WEBHOOK_URL")
    if not url:
        return {"name": "OpenCanary", "status": "FAIL", "detail": "OPEN_CANARY_WEBHOOK_URL not configured"}
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=3) as resp:
            if 200 <= resp.status < 400:
                return {"name": "OpenCanary", "status": "PASS", "detail": "reachable"}
            return {"name": "OpenCanary", "status": "FAIL", "detail": f"HTTP {resp.status}"}
    except Exception as e:
        return {"name": "OpenCanary", "status": "FAIL", "detail": type(e).__name__}


def check_flask():
    url = flask_base_url() + "/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if resp.status == 200 and body.get("status") == "healthy":
                return {"name": "Flask", "status": "PASS", "detail": "health endpoint ok"}
            return {"name": "Flask", "status": "FAIL", "detail": f"HTTP {resp.status} {body}"}
    except Exception as e:
        return {"name": "Flask", "status": "FAIL", "detail": type(e).__name__}


def check_groq():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"name": "Groq", "status": "FAIL", "detail": "GROQ_API_KEY not set"}
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": "Reply with OK"}],
            model=GROQ_MODEL,
            max_tokens=5,
        )
        content = response.choices[0].message.content
        if content and content.strip():
            return {"name": "Groq", "status": "PASS", "detail": "model responding"}
        return {"name": "Groq", "status": "FAIL", "detail": "empty model response"}
    except Exception as e:
        return {"name": "Groq", "status": "FAIL", "detail": type(e).__name__}


def check_telegram():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"name": "Telegram", "status": "FAIL", "detail": "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set"}
    ok = telegram_worker.send_telegram_message(PREFLIGHT_TELEGRAM_MESSAGE)
    if ok:
        return {"name": "Telegram", "status": "PASS", "detail": "test message delivered"}
    return {"name": "Telegram", "status": "FAIL", "detail": "delivery failed"}


def check_sqlite():
    db_path = db.DEFAULT_DB_PATH
    if not os.path.exists(db_path):
        return {"name": "SQLite", "status": "FAIL", "detail": f"{db_path} missing"}
    writable = False
    try:
        conn = sqlite3.connect(db_path)
        try:
            conn.execute("BEGIN")
            conn.execute("CREATE TABLE IF NOT EXISTS preflight_probe (id INTEGER)")
            conn.execute("INSERT INTO preflight_probe (id) VALUES (1)")
            row = conn.execute("SELECT COUNT(*) FROM preflight_probe").fetchone()
            writable = bool(row) and row[0] == 1
            conn.execute("ROLLBACK")
        finally:
            conn.close()
    except Exception as e:
        return {"name": "SQLite", "status": "FAIL", "detail": type(e).__name__}
    if writable:
        return {"name": "SQLite", "status": "PASS", "detail": "write verified without residue"}
    return {"name": "SQLite", "status": "FAIL", "detail": "write verification failed"}


def check_echarts():
    path = os.path.join(PROJECT_ROOT, "static", "echarts.min.js")
    if not os.path.exists(path):
        return {"name": "ECharts", "status": "FAIL", "detail": "static/echarts.min.js missing"}
    size = os.path.getsize(path)
    if size < 1000:
        return {"name": "ECharts", "status": "FAIL", "detail": "file looks like a placeholder"}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(512)
    except Exception as e:
        return {"name": "ECharts", "status": "FAIL", "detail": f"unreadable: {type(e).__name__}"}
    if "echarts" not in head.lower() and "apache" not in head.lower():
        return {"name": "ECharts", "status": "FAIL", "detail": "not a real echarts bundle"}
    try:
        url = flask_base_url() + "/static/echarts.min.js"
        with urllib.request.urlopen(url, timeout=3) as resp:
            if resp.status == 200:
                return {"name": "ECharts", "status": "PASS", "detail": "served locally by Flask"}
            return {"name": "ECharts", "status": "FAIL", "detail": f"HTTP {resp.status}"}
    except Exception as e:
        return {"name": "ECharts", "status": "FAIL", "detail": f"not reachable via Flask: {type(e).__name__}"}


def run_all():
    return [
        check_opencanary(),
        check_flask(),
        check_groq(),
        check_telegram(),
        check_sqlite(),
        check_echarts(),
    ]


def main():
    print("PRE-FLIGHT")
    checks = run_all()
    passed = sum(1 for c in checks if c["status"] == "PASS")
    total = len(checks)
    for c in checks:
        print(f"{c['name']} = {c['status']} — {c['detail']}")
    if passed == total:
        print("DEMO READY — 6/6 SYSTEMS ONLINE")
        return 0
    print(f"DEMO NOT READY — {passed}/{total} SYSTEMS ONLINE")
    if checks[0]["status"] == "FAIL":
        print("LIVE MODE UNAVAILABLE — USE REPLAY")
    if checks[4]["status"] == "FAIL":
        print("DEMO NOT READY — SQLITE FAILURE")
    return 1


if __name__ == "__main__":
    sys_exit = main()
    import sys
    sys.exit(sys_exit)

import unittest
import json
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import preflight
import db


class FakeHTTPResponse:
    def __init__(self, status=200, body=b'{}'):
        self.status = status
        self._body = body

    def read(self, *args, **kwargs):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class TestPreflight(unittest.TestCase):

    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        db.DEFAULT_DB_PATH = self.db_path
        db.init_db(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_check_opencanary_not_configured(self):
        with patch.dict(os.environ, {}, clear=True):
            result = preflight.check_opencanary()
        self.assertEqual(result["name"], "OpenCanary")
        self.assertEqual(result["status"], "FAIL")

    def test_check_opencanary_reachable(self):
        with patch.dict(os.environ, {"OPEN_CANARY_WEBHOOK_URL": "http://canary:5000/webhook"}, clear=True):
            with patch('urllib.request.urlopen', return_value=FakeHTTPResponse(200)):
                result = preflight.check_opencanary()
        self.assertEqual(result["status"], "PASS")

    def test_check_opencanary_unreachable(self):
        with patch.dict(os.environ, {"OPEN_CANARY_WEBHOOK_URL": "http://canary:5000/webhook"}, clear=True):
            with patch('urllib.request.urlopen', side_effect=Exception("unreachable")):
                result = preflight.check_opencanary()
        self.assertEqual(result["status"], "FAIL")

    def test_check_flask_healthy(self):
        body = json.dumps({"status": "healthy", "db": "connected"}).encode("utf-8")
        with patch.dict(os.environ, {"PREFLIGHT_FLASK_URL": "http://127.0.0.1:5000"}, clear=True):
            with patch('urllib.request.urlopen', return_value=FakeHTTPResponse(200, body)) as mock_open:
                result = preflight.check_flask()
        self.assertEqual(result["status"], "PASS")
        request_url = mock_open.call_args[0][0]
        self.assertTrue(request_url.endswith("/health"))

    def test_check_flask_unhealthy(self):
        body = json.dumps({"status": "unhealthy"}).encode("utf-8")
        with patch.dict(os.environ, {"PREFLIGHT_FLASK_URL": "http://127.0.0.1:5000"}, clear=True):
            with patch('urllib.request.urlopen', return_value=FakeHTTPResponse(500, body)):
                result = preflight.check_flask()
        self.assertEqual(result["status"], "FAIL")

    def test_check_flask_unreachable(self):
        with patch.dict(os.environ, {"PREFLIGHT_FLASK_URL": "http://127.0.0.1:5000"}, clear=True):
            with patch('urllib.request.urlopen', side_effect=Exception("connection refused")):
                result = preflight.check_flask()
        self.assertEqual(result["status"], "FAIL")

    def test_check_groq_no_key(self):
        with patch.dict(os.environ, {}, clear=True):
            result = preflight.check_groq()
        self.assertEqual(result["status"], "FAIL")

    def test_check_groq_success(self):
        class FakeCompletions:
            def create(self, **kwargs):
                return type('obj', (object,), {
                    'choices': [type('obj', (object,), {
                        'message': type('obj', (object,), {'content': 'OK'})
                    })()]
                })

        class FakeChat:
            completions = FakeCompletions()

        class FakeGroq:
            def __init__(self, api_key=None):
                self.chat = FakeChat()

        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=True):
            with patch('groq.Groq', FakeGroq):
                result = preflight.check_groq()
        self.assertEqual(result["status"], "PASS")

    def test_check_groq_api_failure(self):
        class FailingCompletions:
            def create(self, **kwargs):
                raise Exception("API error")

        class FakeChat:
            completions = FailingCompletions()

        class FakeGroq:
            def __init__(self, api_key=None):
                self.chat = FakeChat()

        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}, clear=True):
            with patch('groq.Groq', FakeGroq):
                result = preflight.check_groq()
        self.assertEqual(result["status"], "FAIL")

    def test_check_telegram_no_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            result = preflight.check_telegram()
        self.assertEqual(result["status"], "FAIL")

    def test_check_telegram_delivered(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}, clear=True):
            with patch('telegram_worker.send_telegram_message', return_value=True) as mock_send:
                result = preflight.check_telegram()
        self.assertEqual(result["status"], "PASS")
        mock_send.assert_called_once_with("INTRUDER INVISIBLE — PRE-FLIGHT TEST")

    def test_check_telegram_delivery_failed(self):
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}, clear=True):
            with patch('telegram_worker.send_telegram_message', return_value=False):
                result = preflight.check_telegram()
        self.assertEqual(result["status"], "FAIL")

    def test_check_sqlite_writable(self):
        result = preflight.check_sqlite()
        self.assertEqual(result["status"], "PASS")
        events = db.get_events(self.db_path)
        self.assertEqual(len(events), 0)

    def test_check_sqlite_missing(self):
        db.DEFAULT_DB_PATH = os.path.join(tempfile.mkdtemp(), "missing.sqlite3")
        result = preflight.check_sqlite()
        self.assertEqual(result["status"], "FAIL")

    def test_check_echarts_served_locally(self):
        with patch.dict(os.environ, {"PREFLIGHT_FLASK_URL": "http://127.0.0.1:5000"}, clear=True):
            with patch('urllib.request.urlopen', return_value=FakeHTTPResponse(200)) as mock_open:
                result = preflight.check_echarts()
        self.assertEqual(result["status"], "PASS")
        request_url = mock_open.call_args[0][0]
        self.assertTrue(request_url.endswith("/static/echarts.min.js"))

    def test_check_echarts_missing_file(self):
        tmpdir = tempfile.mkdtemp()
        with patch('preflight.PROJECT_ROOT', tmpdir):
            result = preflight.check_echarts()
        self.assertEqual(result["status"], "FAIL")

    def test_check_echarts_placeholder_file(self):
        tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmpdir, "static"), exist_ok=True)
        with open(os.path.join(tmpdir, "static", "echarts.min.js"), "w") as f:
            f.write("placeholder")
        with patch('preflight.PROJECT_ROOT', tmpdir):
            result = preflight.check_echarts()
        self.assertEqual(result["status"], "FAIL")

    def test_run_all_returns_six_checks(self):
        results = preflight.run_all()
        self.assertEqual(len(results), 6)
        names = [r["name"] for r in results]
        self.assertEqual(names, ["OpenCanary", "Flask", "Groq", "Telegram", "SQLite", "ECharts"])
        for r in results:
            self.assertIn(r["status"], ("PASS", "FAIL"))
            self.assertIn("name", r)
            self.assertIn("detail", r)

    def test_main_all_pass(self):
        all_pass = [
            {"name": "OpenCanary", "status": "PASS", "detail": "ok"},
            {"name": "Flask", "status": "PASS", "detail": "ok"},
            {"name": "Groq", "status": "PASS", "detail": "ok"},
            {"name": "Telegram", "status": "PASS", "detail": "ok"},
            {"name": "SQLite", "status": "PASS", "detail": "ok"},
            {"name": "ECharts", "status": "PASS", "detail": "ok"},
        ]
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch('preflight.run_all', return_value=all_pass):
            with redirect_stdout(buf):
                code = preflight.main()
        self.assertEqual(code, 0)
        output = buf.getvalue()
        self.assertIn("DEMO READY — 6/6 SYSTEMS ONLINE", output)

    def test_main_partial_failure(self):
        partial = [
            {"name": "OpenCanary", "status": "FAIL", "detail": "not configured"},
            {"name": "Flask", "status": "PASS", "detail": "ok"},
            {"name": "Groq", "status": "PASS", "detail": "ok"},
            {"name": "Telegram", "status": "PASS", "detail": "ok"},
            {"name": "SQLite", "status": "PASS", "detail": "ok"},
            {"name": "ECharts", "status": "PASS", "detail": "ok"},
        ]
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch('preflight.run_all', return_value=partial):
            with redirect_stdout(buf):
                code = preflight.main()
        self.assertEqual(code, 1)
        output = buf.getvalue()
        self.assertIn("DEMO NOT READY — 5/6 SYSTEMS ONLINE", output)
        self.assertIn("LIVE MODE UNAVAILABLE — USE REPLAY", output)

    def test_main_sqlite_failure(self):
        sqlite_fail = [
            {"name": "OpenCanary", "status": "FAIL", "detail": "not configured"},
            {"name": "Flask", "status": "PASS", "detail": "ok"},
            {"name": "Groq", "status": "PASS", "detail": "ok"},
            {"name": "Telegram", "status": "PASS", "detail": "ok"},
            {"name": "SQLite", "status": "FAIL", "detail": "missing"},
            {"name": "ECharts", "status": "PASS", "detail": "ok"},
        ]
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch('preflight.run_all', return_value=sqlite_fail):
            with redirect_stdout(buf):
                code = preflight.main()
        self.assertEqual(code, 1)
        output = buf.getvalue()
        self.assertIn("DEMO NOT READY — 4/6 SYSTEMS ONLINE", output)
        self.assertIn("DEMO NOT READY — SQLITE FAILURE", output)


if __name__ == '__main__':
    unittest.main()

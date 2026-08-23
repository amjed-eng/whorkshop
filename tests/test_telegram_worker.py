import unittest
import os
import queue
import tempfile
import sys
import threading
from unittest.mock import patch
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app
import db
import state
import telegram_worker

class MockResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

class MockOpener:
    def __init__(self):
        self.requests = []
        self.fail_next = None
        self.status_next = 200

    def open(self, req, timeout=None):
        self.requests.append(req)
        if self.fail_next:
            err = self.fail_next
            self.fail_next = None
            raise err
        return MockResponse(self.status_next)

class TestTelegramWorker(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        db.DEFAULT_DB_PATH = self.db_path
        db.init_db(self.db_path)
        state.reset_state()
        telegram_worker.reset_deduplication()
        self.opener = MockOpener()
        self.worker = telegram_worker.create_telegram_worker_callback(opener=self.opener)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_token_or_chat_id(self):
        # 1. missing token
        task = {"generation": state.get_generation(), "event_id": 1, "message": "msg"}
        self.worker(task)
        self.assertEqual(len(self.opener.requests), 0)

        # 2. missing chat ID
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token"}):
            self.worker(task)
            self.assertEqual(len(self.opener.requests), 0)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_malformed_task(self):
        # 3. malformed task
        self.worker(None)
        self.worker({"event_id": 1})
        self.worker({"generation": state.get_generation(), "event_id": 1})
        self.assertEqual(len(self.opener.requests), 0)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_stale_generation_discarded(self):
        # 4. stale generation discarded
        old_gen = state.get_generation()
        state.reset_state()
        task = {"generation": old_gen, "event_id": 1, "message": "msg"}
        self.worker(task)
        self.assertEqual(len(self.opener.requests), 0)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_successful_send(self):
        # 5. successful sendMessage
        task = {"generation": state.get_generation(), "event_id": 1, "message": "msg"}
        self.worker(task)
        self.assertEqual(len(self.opener.requests), 1)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_http_500(self):
        # 6. HTTP 500
        self.opener.status_next = 500
        task = {"generation": state.get_generation(), "event_id": 1, "message": "msg"}
        self.worker(task)
        self.assertEqual(len(self.opener.requests), 1)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_network_exception(self):
        # 7. network exception
        self.opener.fail_next = Exception("Network down")
        task = {"generation": state.get_generation(), "event_id": 1, "message": "msg"}
        self.worker(task)
        self.assertEqual(len(self.opener.requests), 1)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_timeout(self):
        # 8. timeout
        self.opener.fail_next = urllib.error.URLError("Timeout")
        task = {"generation": state.get_generation(), "event_id": 1, "message": "msg"}
        self.worker(task)
        self.assertEqual(len(self.opener.requests), 1)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_deduplication(self):
        # 9. duplicate same (generation,event_id) sent once
        task = {"generation": state.get_generation(), "event_id": 1, "message": "msg"}
        self.worker(task)
        self.worker(task)
        self.assertEqual(len(self.opener.requests), 1)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_reset_dedup(self):
        # 10. reset dedup allows same event identity in new/reset context
        task = {"generation": state.get_generation(), "event_id": 1, "message": "msg"}
        self.worker(task)
        self.assertEqual(len(self.opener.requests), 1)
        
        telegram_worker.reset_deduplication()
        state.reset_state() # new generation
        task["generation"] = state.get_generation()
        self.worker(task)
        self.assertEqual(len(self.opener.requests), 2)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_telegram_failure_isolation(self):
        # 11 & 12. Telegram failure does not affect state or SQLite
        self.opener.fail_next = Exception("Crash")
        db.save_event("t", "10.0.0.1", "SSH", "Login", "hash")
        state_snapshot = state.get_snapshot()
        task = {"generation": state.get_generation(), "event_id": 1, "message": "msg"}
        self.worker(task)
        self.assertEqual(state_snapshot, state.get_snapshot())
        self.assertEqual(len(db.get_events()), 1)

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True)
    def test_worker_survives_failed_task(self):
        # 13. Telegram Worker survives failed task and processes next task
        self.opener.fail_next = Exception("Crash")
        task1 = {"generation": state.get_generation(), "event_id": 1, "message": "msg1"}
        task2 = {"generation": state.get_generation(), "event_id": 2, "message": "msg2"}
        self.worker(task1)
        self.worker(task2)
        self.assertEqual(len(self.opener.requests), 2)

    def test_start_runtime_workers_lifecycle(self):
        # Stop everything
        if app._ai_thread and app._ai_thread.is_alive():
            app.ai_queue.put(None)
            app._ai_thread.join(timeout=2)
        if app._telegram_thread and app._telegram_thread.is_alive():
            app.telegram_queue.put(None)
            app._telegram_thread.join(timeout=2)
            
        app._worker_started = False
        app._ai_thread = None
        app._telegram_thread = None
        
        # 14. start_runtime_workers() remains idempotent with both workers
        app.start_runtime_workers()
        self.assertIsNotNone(app._ai_thread)
        self.assertIsNotNone(app._telegram_thread)
        self.assertTrue(app._telegram_thread.is_alive())
        
        t_ai = app._ai_thread
        t_tele = app._telegram_thread
        
        app.start_runtime_workers()
        self.assertIs(t_ai, app._ai_thread)
        self.assertIs(t_tele, app._telegram_thread)
        
        # 15. dead Telegram thread can be restarted
        app.telegram_queue.put(None)
        app._telegram_thread.join(timeout=2)
        self.assertFalse(app._telegram_thread.is_alive())
        
        app.start_runtime_workers()
        self.assertIsNot(t_tele, app._telegram_thread)
        self.assertTrue(app._telegram_thread.is_alive())
        
        # 16. AI thread remains unaffected by Telegram failure
        self.assertIs(t_ai, app._ai_thread)
        
        # Cleanup
        app.ai_queue.put(None)
        app.telegram_queue.put(None)
        app._ai_thread.join(timeout=2)
        app._telegram_thread.join(timeout=2)

if __name__ == '__main__':
    unittest.main()

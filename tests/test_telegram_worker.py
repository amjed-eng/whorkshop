import unittest
import json
import os
from unittest.mock import patch, MagicMock

import state
import telegram_worker

class TestTelegramWorker(unittest.TestCase):
    def setUp(self):
        state.reset_state()
        self.worker = telegram_worker.create_worker_callback()
        
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_CHAT_ID": "mock_chat_id"})
    @patch("urllib.request.urlopen")
    def test_success_path(self, mock_urlopen):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        task = {
            "event_id": 1,
            "generation": state.get_generation(),
            "message": "EMERGENCY ALERT"
        }
        
        self.worker(task)
        
        # Verify network call
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        
        self.assertEqual(req.full_url, "https://api.telegram.org/botmock_token/sendMessage")
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.headers.get("Content-type"), "application/json")
        
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["chat_id"], "mock_chat_id")
        self.assertEqual(payload["text"], "EMERGENCY ALERT")
        self.assertEqual(payload["parse_mode"], "Markdown")

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_CHAT_ID": "mock_chat_id"})
    @patch("urllib.request.urlopen")
    def test_stale_generation_rejected(self, mock_urlopen):
        old_gen = state.get_generation()
        state.reset_state() # Increments generation
        
        task = {
            "event_id": 1,
            "generation": old_gen,
            "message": "EMERGENCY ALERT"
        }
        
        self.worker(task)
        
        # Verify NO network call was made
        mock_urlopen.assert_not_called()

    @patch.dict(os.environ, {}, clear=True)
    @patch("urllib.request.urlopen")
    def test_missing_env_vars(self, mock_urlopen):
        task = {
            "event_id": 1,
            "generation": state.get_generation(),
            "message": "EMERGENCY ALERT"
        }
        
        self.worker(task)
        
        # Verify NO network call was made
        mock_urlopen.assert_not_called()

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_CHAT_ID": "mock_chat_id"})
    @patch("urllib.request.urlopen")
    def test_api_failure_handled(self, mock_urlopen):
        # Test 500 error
        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.read.return_value = b'Internal Server Error'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        task = {
            "event_id": 1,
            "generation": state.get_generation(),
            "message": "EMERGENCY ALERT"
        }
        
        # Should not raise exception
        self.worker(task)
        mock_urlopen.assert_called_once()
        
    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_CHAT_ID": "mock_chat_id"})
    @patch("urllib.request.urlopen")
    def test_network_exception_handled(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        task = {
            "event_id": 1,
            "generation": state.get_generation(),
            "message": "EMERGENCY ALERT"
        }
        
        # Should not raise exception
        self.worker(task)
        mock_urlopen.assert_called_once()

    @patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "mock_token", "TELEGRAM_CHAT_ID": "mock_chat_id"})
    @patch("urllib.request.urlopen")
    def test_malformed_task(self, mock_urlopen):
        # Missing event_id
        task1 = {"generation": state.get_generation(), "message": "EMERGENCY ALERT"}
        # Missing generation
        task2 = {"event_id": 1, "message": "EMERGENCY ALERT"}
        # Missing message
        task3 = {"event_id": 1, "generation": state.get_generation()}
        
        self.worker(task1)
        self.worker(task2)
        self.worker(task3)
        
        mock_urlopen.assert_not_called()

if __name__ == "__main__":
    unittest.main()

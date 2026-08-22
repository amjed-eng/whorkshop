import unittest
import json
import queue
import tempfile
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import tests.flask_patch
import tests.groq_patch

import db
import state
import ai_worker
import prompt

class FakeMessage:
    def __init__(self, content):
        self.content = content

class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)

class FakeCompletions:
    def __init__(self, client):
        self.client = client
        self.last_kwargs = None
        
    def create(self, **kwargs):
        self.last_kwargs = kwargs
        if self.client.fail_next:
            self.client.fail_next = False
            raise Exception("Mock Groq API Failure")
        return self.client.mock_response

class FakeChat:
    def __init__(self, client):
        self.completions = FakeCompletions(client)

class FakeGroqClient:
    def __init__(self):
        self.chat = FakeChat(self)
        self.mock_response = None
        self.fail_next = False
        
    def set_response(self, result_dict):
        content = json.dumps(result_dict)
        self.mock_response = type('obj', (object,), {'choices': [FakeChoice(content)]})

class TestAIWorker(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        db.DEFAULT_DB_PATH = self.db_path
        db.init_db(self.db_path)
        state.reset_state()
        
        self.telegram_queue = queue.Queue()
        self.broadcasts = []
        
        def broadcast_callback(kind, payload):
            self.broadcasts.append((kind, payload))
            
        self.broadcast_callback = broadcast_callback
        self.groq_client = FakeGroqClient()
        self.worker = ai_worker.create_worker_callback(self.telegram_queue, self.broadcast_callback, self.groq_client)
        
        self.valid_result = {
            "event_type": "Login", "source": "10.0.0.1", "target_service": "SSH",
            "timestamp": "t", "attempt_count": 1, "previous_related_events": [],
            "current_risk_context": {}, "severity": "HIGH", "risk_score": 75,
            "stage": "Discovery", "executive_title": "Title", "executive_summary": "Sum",
            "business_impact": "Impact", "recommended_action": "Action", "telegram_alert": ""
        }

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_valid_result_accepted(self):
        event_id = db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=21)
        task = {"event_id": event_id, "generation": state.get_generation(), "normalized_event": {}}
        
        self.groq_client.set_response(self.valid_result)
        self.worker(task)
        
        # Check SQLite
        events = db.get_events(self.db_path)
        self.assertEqual(events[0]["risk"], 75)
        self.assertEqual(json.loads(events[0]["ai_classification"]), self.valid_result)
        
        # Check state
        self.assertEqual(state.get_snapshot()["ai_result"], self.valid_result)
        
        # Check broadcast
        self.assertEqual(len(self.broadcasts), 1)
        self.assertEqual(self.broadcasts[0][0], "AI_RESULT")
        
        # Check telegram
        self.assertTrue(self.telegram_queue.empty())
        
        # Check Groq API arguments
        kwargs = self.groq_client.chat.completions.last_kwargs
        self.assertIsNotNone(kwargs)
        self.assertEqual(kwargs["model"], "openai/gpt-oss-20b")
        self.assertEqual(kwargs["response_format"]["type"], "json_schema")
        
        schema = kwargs["response_format"]["json_schema"]["schema"]
        self.assertTrue(kwargs["response_format"]["json_schema"]["strict"])
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        
        required_fields = ["severity", "risk_score", "stage", "executive_title", "executive_summary", "business_impact", "recommended_action", "telegram_alert"]
        for field in required_fields:
            self.assertIn(field, schema["required"])
            self.assertIn(field, schema["properties"])
        
        # ai_worker.py actually requires 15 fields total
        self.assertEqual(len(schema["required"]), 15)
        
        # Check prompt data minimization
        messages = kwargs["messages"]
        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        # Ensure the raw_event_hash and other raw wrapper properties are NOT in the prompt
        self.assertNotIn("hash", user_msg)
        self.assertNotIn("event_id", user_msg)
        self.assertNotIn("generation", user_msg)

    def test_invalid_schema_rejected(self):
        event_id = db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=21)
        task = {"event_id": event_id, "generation": state.get_generation(), "normalized_event": {}}
        
        invalid_res_missing = self.valid_result.copy()
        del invalid_res_missing["severity"] # missing field
        
        self.groq_client.set_response(invalid_res_missing)
        self.worker(task)
        self.assertIsNone(state.get_snapshot()["ai_result"])
        
        invalid_res_extra = self.valid_result.copy()
        invalid_res_extra["extra_unexpected_field"] = "value"
        
        self.groq_client.set_response(invalid_res_extra)
        self.worker(task)
        self.assertIsNone(state.get_snapshot()["ai_result"])
        
        self.assertEqual(len(self.broadcasts), 0)

    def test_risk_score_invalid_rejected(self):
        event_id = db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=21)
        task = {"event_id": event_id, "generation": state.get_generation(), "normalized_event": {}}
        
        invalid_res = self.valid_result.copy()
        invalid_res["risk_score"] = 150 # > 100
        
        self.groq_client.set_response(invalid_res)
        self.worker(task)
        
        self.assertIsNone(state.get_snapshot()["ai_result"])

    def test_old_generation_before_groq(self):
        event_id = db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=21)
        old_gen = state.get_generation()
        state.reset_state() # gen increments
        
        task = {"event_id": event_id, "generation": old_gen, "normalized_event": {}}
        self.groq_client.set_response(self.valid_result)
        
        from unittest.mock import patch
        with patch('db.update_ai_classification') as mock_db_update:
            self.worker(task)
            
            self.assertIsNone(state.get_snapshot()["ai_result"])
            self.assertIsNone(self.groq_client.chat.completions.last_kwargs)
            mock_db_update.assert_not_called()
            self.assertEqual(len(self.broadcasts), 0)
            self.assertTrue(self.telegram_queue.empty())

    def test_reset_in_flight_rejected(self):
        event_id = db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=21)
        old_gen = state.get_generation()
        task = {"event_id": event_id, "generation": old_gen, "normalized_event": {}}
        
        # We need to simulate reset happening WHILE in Groq call
        class DelayCompletions:
            def create(self, **kwargs):
                state.reset_state() # Reset while in flight!
                content = json.dumps(self.valid_result)
                from tests.test_ai_worker import FakeChoice
                return type('obj', (object,), {'choices': [FakeChoice(content)]})
                
        self.groq_client.chat.completions = DelayCompletions()
        self.groq_client.chat.completions.valid_result = self.valid_result
        
        from unittest.mock import patch
        with patch('db.update_ai_classification') as mock_db_update:
            self.worker(task)
            
            # Generation changed, so result should be discarded
            self.assertIsNone(state.get_snapshot()["ai_result"])
            mock_db_update.assert_not_called()
            self.assertEqual(len(self.broadcasts), 0)
            self.assertTrue(self.telegram_queue.empty())

    def test_telegram_enqueue_critical_with_alert(self):
        event_id = db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=21)
        task = {"event_id": event_id, "generation": state.get_generation(), "normalized_event": {}}
        
        crit_res = self.valid_result.copy()
        crit_res["severity"] = "CRITICAL"
        crit_res["telegram_alert"] = "EMERGENCY: Hack detected"
        
        self.groq_client.set_response(crit_res)
        self.worker(task)
        
        self.assertFalse(self.telegram_queue.empty())
        t_task = self.telegram_queue.get()
        self.assertEqual(t_task["message"], "EMERGENCY: Hack detected")

    def test_telegram_no_enqueue_non_critical_with_alert(self):
        event_id = db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=21)
        task = {"event_id": event_id, "generation": state.get_generation(), "normalized_event": {}}
        
        non_crit_res = self.valid_result.copy()
        non_crit_res["severity"] = "HIGH"
        non_crit_res["telegram_alert"] = "Should not alert"
        
        self.groq_client.set_response(non_crit_res)
        self.worker(task)
        
        self.assertTrue(self.telegram_queue.empty())

    def test_telegram_no_enqueue_critical_empty_alert(self):
        event_id = db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=21)
        task = {"event_id": event_id, "generation": state.get_generation(), "normalized_event": {}}
        
        crit_res = self.valid_result.copy()
        crit_res["severity"] = "CRITICAL"
        crit_res["telegram_alert"] = "   " # Empty/spaces
        
        self.groq_client.set_response(crit_res)
        self.worker(task)
        
        self.assertTrue(self.telegram_queue.empty())

    def test_groq_exception_handled(self):
        event_id = db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=21)
        task = {"event_id": event_id, "generation": state.get_generation(), "normalized_event": {}}
        
        self.groq_client.fail_next = True
        
        # Should not raise exception
        self.worker(task)
        self.assertIsNone(state.get_snapshot()["ai_result"])
        
    def test_missing_groq_api_key_handled(self):
        # Pass None to simulate missing key
        worker = ai_worker.create_worker_callback(self.telegram_queue, self.broadcast_callback, None)
        task = {"event_id": 1, "generation": state.get_generation(), "normalized_event": {}}
        # Should just log and return safely
        worker(task)
        
        # Also ensure app.py logic handles missing key safely
        from unittest.mock import patch
        import os
        with patch.dict(os.environ, {}, clear=True):
            import app
            self.assertIsNotNone(app.app)

if __name__ == '__main__':
    unittest.main()

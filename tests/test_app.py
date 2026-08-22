import unittest
import json
import tempfile
import os
import queue

import sys
import os

# Inject flask and groq patches before app imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import tests.flask_patch
import tests.groq_patch

import app
import db
import state

class TestApp(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        db.DEFAULT_DB_PATH = self.db_path
        db.init_db(self.db_path)
        
        state.reset_state()
        
        # Clear ai queue
        while not app.ai_queue.empty():
            app.ai_queue.get()
            
        app.app.config['TESTING'] = True
        self.client = app.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_get_index(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["service"], "INTRUDER_INVISIBLE")

    def test_get_health(self):
        # Healthy case
        resp = self.client.get('/health')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "healthy")
        
        # Broken case
        from unittest.mock import patch
        with patch('db.get_events', side_effect=Exception("DB Error")):
            resp_broken = self.client.get('/health')
            self.assertEqual(resp_broken.status_code, 500)
            self.assertEqual(resp_broken.get_json()["status"], "unhealthy")

    def test_invalid_webhook_not_json(self):
        resp = self.client.post('/webhook/opencanary', data="not json")
        self.assertEqual(resp.status_code, 400)

    def test_invalid_webhook_missing_fields(self):
        base_payload = {
            "event_type": "Login Attempt", "source": "10.0.0.1", "target_service": "SSH",
            "timestamp": "2026-08-23T00:00:00Z", "attempt_count": 1,
            "previous_related_events": [], "current_risk_context": {}
        }
        for field in ["event_type", "source", "target_service", "timestamp", "attempt_count", "previous_related_events", "current_risk_context"]:
            with self.subTest(field=field):
                payload = base_payload.copy()
                del payload[field]
                resp = self.client.post('/webhook/opencanary', json=payload)
                self.assertEqual(resp.status_code, 400)
                
    def test_invalid_webhook_wrong_types(self):
        base_payload = {
            "event_type": "Login Attempt", "source": "10.0.0.1", "target_service": "SSH",
            "timestamp": "2026-08-23T00:00:00Z", "attempt_count": 1,
            "previous_related_events": [], "current_risk_context": {}
        }
        cases = [
            ("attempt_count", 0),
            ("attempt_count", "not_int"),
            ("previous_related_events", "not_list"),
            ("current_risk_context", "not_dict"),
            ("current_risk_context", {"risk_score": -1}),
            ("current_risk_context", {"risk_score": 101}),
            ("current_risk_context", {"risk_score": "not_int"})
        ]
        for field, bad_val in cases:
            with self.subTest(field=field, bad_val=bad_val):
                payload = base_payload.copy()
                payload[field] = bad_val
                resp = self.client.post('/webhook/opencanary', json=payload)
                self.assertEqual(resp.status_code, 400)

    def test_valid_webhook(self):
        payload = {
            "event_type": "Login Attempt",
            "source": "10.0.0.1",
            "target_service": "SSH",
            "timestamp": "2026-08-23T00:00:00Z",
            "attempt_count": 1,
            "previous_related_events": [],
            "current_risk_context": {}
        }
        resp = self.client.post('/webhook/opencanary', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["accepted"])
        self.assertIn("event_id", data)
        self.assertIn("generation", data)
        
        # Check SQLite row
        events = db.get_events(self.db_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "10.0.0.1")
        self.assertEqual(events[0]["risk"], 21) # First event risk
        
        # Check AI Queue
        self.assertFalse(app.ai_queue.empty())
        task = app.ai_queue.get()
        self.assertEqual(task["event_id"], events[0]["event_id"])
        
        # Check local state updated
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["current_state"], state.UNDER_OBSERVATION)
        self.assertEqual(snapshot["current_risk"], 21)
        
    def test_webhook_execution_order(self):
        from unittest.mock import patch, call
        
        payload = {
            "event_type": "Login Attempt", "source": "10.0.0.1", "target_service": "SSH",
            "timestamp": "2026-08-23T00:00:00Z", "attempt_count": 1,
            "previous_related_events": [], "current_risk_context": {}
        }
        
        with patch('app.normalize_event', side_effect=app.normalize_event) as mock_normalize, \
             patch('app.generate_hash', side_effect=app.generate_hash) as mock_hash, \
             patch('db.save_event', return_value=999) as mock_save, \
             patch('state.process_event', return_value={"state": state.UNDER_OBSERVATION, "risk": 21}) as mock_process, \
             patch('db.update_event_risk') as mock_update_risk, \
             patch('app.broadcast_message') as mock_broadcast, \
             patch('app.ai_queue.put') as mock_put:
             
             from unittest.mock import Mock
             manager = Mock()
             manager.attach_mock(mock_normalize, 'normalize')
             manager.attach_mock(mock_hash, 'hash')
             manager.attach_mock(mock_save, 'save')
             manager.attach_mock(mock_process, 'process')
             manager.attach_mock(mock_update_risk, 'update_risk')
             manager.attach_mock(mock_broadcast, 'broadcast')
             manager.attach_mock(mock_put, 'put')
             
             resp = self.client.post('/webhook/opencanary', json=payload)
             self.assertEqual(resp.status_code, 200)
             
             # Calculate hash string once for assertion
             hash_str = app.generate_hash(payload)
             
             expected_calls = [
                 call.normalize(payload),
                 call.hash(payload),
                 call.save(timestamp=payload['timestamp'], source=payload['source'], service=payload['target_service'], event_type=payload['event_type'], raw_event_hash=hash_str, risk=0),
                 call.process(payload),
                 call.update_risk(999, 21),
                 call.broadcast('EVENT', {"event_id": 999, "normalized": payload}),
                 call.broadcast('STATE', state.get_snapshot()),
                 call.put({"event_id": 999, "generation": state.get_generation(), "normalized_event": payload, "raw_event_hash": hash_str})
             ]
             manager.assert_has_calls(expected_calls, any_order=False)

    def test_hash_stability(self):
        j1 = {"a": 1, "b": 2}
        j2 = {"b": 2, "a": 1}
        self.assertEqual(app.generate_hash(j1), app.generate_hash(j2))
        
    def test_db_failure_isolation(self):
        # Break DB to ensure it returns 500 and doesn't mutate state
        db.DEFAULT_DB_PATH = "/invalid/path/db.sqlite3"
        payload = {
            "event_type": "Login Attempt", "source": "10.0.0.1", "target_service": "SSH",
            "timestamp": "t", "attempt_count": 1, "previous_related_events": [], "current_risk_context": {}
        }
        from unittest.mock import patch
        with patch('app.broadcast_message') as mock_broadcast:
            resp = self.client.post('/webhook/opencanary', json=payload)
            self.assertEqual(resp.status_code, 500)
            self.assertEqual(state.get_snapshot()["current_risk"], 0)
            self.assertTrue(app.ai_queue.empty())
            mock_broadcast.assert_not_called()

    def test_reset_clears_db_and_increments_gen(self):
        self.client.post('/webhook/opencanary', json={
            "event_type": "L", "source": "10.0.0.1", "target_service": "SSH", "timestamp": "t",
            "attempt_count": 1, "previous_related_events": [], "current_risk_context": {}
        })
        
        events = db.get_events(self.db_path)
        self.assertEqual(len(events), 1)
        gen1 = state.get_generation()
        
        from unittest.mock import patch
        with patch('app.broadcast_message') as mock_broadcast:
            resp = self.client.post('/demo/reset')
            self.assertEqual(resp.status_code, 200)
            
            # Verify RESET broadcast
            snapshot = state.get_snapshot()
            mock_broadcast.assert_called_with("RESET", snapshot)
        
        events_after = db.get_events(self.db_path)
        self.assertEqual(len(events_after), 0)
        
        gen2 = state.get_generation()
        self.assertGreater(gen2, gen1)
        self.assertEqual(snapshot["current_risk"], 0)
        self.assertEqual(snapshot["current_state"], state.NORMAL)
        self.assertEqual(snapshot["timeline"], [])

    def test_contain(self):
        resp = self.client.post('/contain')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(state.get_snapshot()["current_state"], state.CONTAINED)

    def test_executive(self):
        resp = self.client.post('/executive')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(state.get_snapshot()["current_state"], state.EXECUTIVE)

    def test_crime_scene_empty(self):
        resp = self.client.post('/crime-scene')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsNone(data["Evidence 01 - First Seen"])
        self.assertIsNone(data["Evidence 02 - Origin"])
        
    def test_crime_scene_no_critical(self):
        self.client.post('/webhook/opencanary', json={
            "event_type": "Login Attempt", "source": "10.0.0.1", "target_service": "SSH", "timestamp": "t1",
            "attempt_count": 1, "previous_related_events": [], "current_risk_context": {}
        })
        resp = self.client.post('/crime-scene')
        data = resp.get_json()
        self.assertIsNone(data["Evidence 05 - Critical Transition"])
        
    def test_crime_scene_local_critical(self):
        self.client.post('/webhook/opencanary', json={
            "event_type": "Admin Access", "source": "10.0.0.1", "target_service": "Admin System", "timestamp": "t1",
            "attempt_count": 1, "previous_related_events": [], "current_risk_context": {}
        })
        resp = self.client.post('/crime-scene')
        data = resp.get_json()
        self.assertEqual(data["Evidence 05 - Critical Transition"], "Admin Access")
        
    def test_crime_scene_ai_critical(self):
        # Insert a benign event that gets AI escalated
        resp_webhook = self.client.post('/webhook/opencanary', json={
            "event_type": "Data Read", "source": "10.0.0.1", "target_service": "MySQL", "timestamp": "t1",
            "attempt_count": 1, "previous_related_events": [], "current_risk_context": {}
        })
        event_id = resp_webhook.get_json()["event_id"]
        
        # Simulate AI classifying as CRITICAL
        import json
        ai_res = {"severity": "CRITICAL", "risk_score": 95}
        db.update_ai_classification(event_id, ai_res, 95, self.db_path)
        
        resp = self.client.post('/crime-scene')
        data = resp.get_json()
        self.assertEqual(data["Evidence 05 - Critical Transition"], "Data Read")
        
    def test_crime_scene_ordering(self):
        # Insert evidence in specific order to test SQLite ordering
        self.client.post('/webhook/opencanary', json={
            "event_type": "Login Attempt", "source": "10.0.0.1", "target_service": "SSH", "timestamp": "t1",
            "attempt_count": 1, "previous_related_events": [], "current_risk_context": {}
        })
        self.client.post('/webhook/opencanary', json={
            "event_type": "Port Scan", "source": "10.0.0.1", "target_service": "Web", "timestamp": "t2",
            "attempt_count": 1, "previous_related_events": [], "current_risk_context": {}
        })
        
        resp = self.client.post('/crime-scene')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        
        self.assertEqual(data["Evidence 01 - First Seen"], "t1")
        self.assertEqual(data["Evidence 02 - Origin"], "10.0.0.1")
        self.assertEqual(data["Evidence 03 - First Target"], "SSH")
        self.assertEqual(data["Evidence 04 - Activity Sequence"], ["SSH", "Web"])
        
        self.assertEqual(state.get_snapshot()["current_state"], state.FORENSIC)

    def test_events_stream(self):
        # We need to test the generator directly since test_client stream reading is tricky
        import json
        resp = self.client.get('/events')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'text/event-stream')
        
        # Test generator directly
        generator = resp.response
        
        # First yield should be the init snapshot
        first_frame = next(generator)
        self.assertTrue(first_frame.startswith("data: "))
        self.assertTrue(first_frame.endswith("\n\n"))
        
        data_json = json.loads(first_frame[6:-2])
        self.assertEqual(data_json["kind"], "STATE")
        self.assertIn("timeline", data_json["payload"])
        
        # Ensure cleanup works
        self.assertEqual(len(app.subscribers), 1)
        sub_queue = app.subscribers[0]
        
        # Trigger cleanup by closing generator
        generator.close()
        
        # Since the finally block is executed on close, subscribers should be empty
        self.assertEqual(len(app.subscribers), 0)

    def test_background_worker_lifecycle(self):
        # 1. Daemon thread
        threads = [t for t in __import__('threading').enumerate() if t.name == "BackgroundWorker"]
        # In a real app startup this might be running, but in tests we create it manually or it's not started.
        # Let's test the generic start_background_worker function
        import queue
        q = queue.Queue()
        processed = []
        
        def mock_callback(task):
            if task == "fail":
                raise Exception("simulated failure")
            processed.append(task)
            
        t = app.start_background_worker(q, mock_callback, name="TestWorker")
        self.assertTrue(t.daemon)
        
        # 2. Multiple tasks and exception survival
        q.put("ok1")
        q.put("fail")
        q.put("ok2")
        
        q.join() # Wait for all task_done() calls
        
        self.assertEqual(processed, ["ok1", "ok2"])
        
        # Stop worker
        q.put(None)
        t.join(timeout=1)
        self.assertFalse(t.is_alive())

if __name__ == '__main__':
    unittest.main()

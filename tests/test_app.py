import unittest
import json
import tempfile
import os
import queue

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
        resp = self.client.get('/health')
        self.assertEqual(resp.status_code, 200)

    def test_invalid_webhook_not_json(self):
        resp = self.client.post('/webhook/opencanary', data="not json")
        self.assertEqual(resp.status_code, 400)

    def test_invalid_webhook_missing_fields(self):
        resp = self.client.post('/webhook/opencanary', json={"source": "10.0.0.1"})
        self.assertEqual(resp.status_code, 400)

    def test_valid_webhook(self):
        payload = {
            "event_type": "Login Attempt",
            "source": "10.0.0.1",
            "target_service": "SSH",
            "timestamp": "2026-08-23T00:00:00Z"
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

    def test_reset_clears_db_and_increments_gen(self):
        self.client.post('/webhook/opencanary', json={
            "event_type": "L", "source": "10.0.0.1", "target_service": "SSH", "timestamp": "t"
        })
        
        events = db.get_events(self.db_path)
        self.assertEqual(len(events), 1)
        gen1 = state.get_generation()
        
        resp = self.client.post('/demo/reset')
        self.assertEqual(resp.status_code, 200)
        
        events_after = db.get_events(self.db_path)
        self.assertEqual(len(events_after), 0)
        
        gen2 = state.get_generation()
        self.assertGreater(gen2, gen1)

    def test_contain(self):
        resp = self.client.post('/contain')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(state.get_snapshot()["current_state"], state.CONTAINED)

    def test_executive(self):
        resp = self.client.post('/executive')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(state.get_snapshot()["current_state"], state.EXECUTIVE)

    def test_crime_scene(self):
        # Insert evidence
        self.client.post('/webhook/opencanary', json={
            "event_type": "Login Attempt", "source": "10.0.0.1", "target_service": "SSH", "timestamp": "t1"
        })
        self.client.post('/webhook/opencanary', json={
            "event_type": "Admin Access", "source": "10.0.0.1", "target_service": "Admin System", "timestamp": "t2"
        })
        
        resp = self.client.post('/crime-scene')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        
        self.assertEqual(data["Evidence 01 - First Seen"], "t1")
        self.assertEqual(data["Evidence 02 - Origin"], "10.0.0.1")
        self.assertEqual(data["Evidence 03 - First Target"], "SSH")
        self.assertEqual(data["Evidence 04 - Activity Sequence"], ["SSH", "Admin System"])
        self.assertEqual(data["Evidence 05 - Critical Transition"], "Admin Access")
        
        self.assertEqual(state.get_snapshot()["current_state"], state.FORENSIC)

if __name__ == '__main__':
    unittest.main()

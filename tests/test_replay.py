import unittest
import os
import sys
import tempfile
import copy

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app
import db
import state
import replay

class TestReplayMode(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        db.DEFAULT_DB_PATH = self.db_path
        db.init_db(self.db_path)
        state.reset_state()
        self.client = app.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)
        
    def test_events_json_loads_and_expected_events_exist(self):
        events = replay.load_replay_events()
        self.assertEqual(len(events), 3)
        
    def test_every_event_passes_normalize(self):
        events = replay.load_replay_events()
        for ev in events:
            norm = app.normalize_event(ev)
            self.assertIsNotNone(norm)
            
    def test_all_three_share_same_source(self):
        events = replay.load_replay_events()
        src1 = events[0]["source"]
        src2 = events[1]["source"]
        src3 = events[2]["source"]
        self.assertEqual(src1, src2)
        self.assertEqual(src2, src3)
        
    def test_event3_targets_sensitive_service(self):
        events = replay.load_replay_events()
        self.assertEqual(events[2]["target_service"], "Admin System")
        
    def test_invalid_replay_event_number(self):
        resp = self.client.post('/demo/replay/999')
        self.assertEqual(resp.status_code, 404)
        
    def test_replay_1_creates_evidence_and_risk_21(self):
        resp = self.client.post('/demo/replay/1')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(db.get_events(self.db_path)), 1)
        
        snap = state.get_snapshot()
        self.assertEqual(snap["current_risk"], 21)
        
    def test_replay_sequence_risks(self):
        self.client.post('/demo/replay/1')
        self.assertEqual(state.get_snapshot()["current_risk"], 21)
        
        self.client.post('/demo/replay/2')
        self.assertEqual(state.get_snapshot()["current_risk"], 48)
        
        self.client.post('/demo/replay/3')
        snap = state.get_snapshot()
        self.assertEqual(snap["current_risk"], 91)
        self.assertEqual(snap["current_state"], state.CRITICAL_INTRUSION)
        
    def test_reset_clears_replay_state(self):
        self.client.post('/demo/replay/1')
        self.client.post('/demo/reset')
        snap = state.get_snapshot()
        self.assertEqual(snap["current_risk"], 0)
        self.assertEqual(snap["current_state"], state.NORMAL)
        self.assertEqual(len(db.get_events(self.db_path)), 0)

    def test_ai_queue_gets_tasks(self):
        while not app.ai_queue.empty():
            app.ai_queue.get()
            
        self.client.post('/demo/replay/1')
        self.assertFalse(app.ai_queue.empty())

    def test_replay_endpoint_invokes_ingest_event(self):
        from unittest.mock import patch
        with patch('app.ingest_event') as mock_ingest:
            mock_ingest.return_value = {"status": "success", "event_id": 999}
            resp = self.client.post('/demo/replay/1')
            self.assertEqual(resp.status_code, 200)
            mock_ingest.assert_called_once()
            
    def test_sse_broadcast_occurs(self):
        from unittest.mock import patch
        with patch('app.broadcast_message') as mock_broadcast:
            self.client.post('/demo/replay/1')
            mock_broadcast.assert_any_call('EVENT', unittest.mock.ANY)
            mock_broadcast.assert_any_call('STATE', unittest.mock.ANY)
            
    def test_replay_no_synchronous_groq_telegram(self):
        from unittest.mock import patch
        with patch('urllib.request.urlopen') as mock_urlopen:
            self.client.post('/demo/replay/1')
            mock_urlopen.assert_not_called()
            
    def test_old_generation_ai_rejected_in_replay_context(self):
        # Even in replay context, if generation is old, state machine should reject it
        self.client.post('/demo/replay/1')
        snap = state.get_snapshot()
        old_gen = snap["generation"]
        
        # Reset advances generation
        self.client.post('/demo/reset')
        
        # Try to apply ai result for old generation
        state.apply_ai_result({"severity": "CRITICAL"}, old_gen)
        new_snap = state.get_snapshot()
        self.assertIsNone(new_snap.get("ai_result"))
        
    def test_old_generation_telegram_rejected_in_replay_context(self):
        import telegram_worker
        from unittest.mock import patch
        
        self.client.post('/demo/replay/1')
        snap = state.get_snapshot()
        old_gen = snap["generation"]
        
        self.client.post('/demo/reset')
        
        task = {
            "event_id": 1,
            "generation": old_gen,
            "message": "CRITICAL from Old Gen"
        }
        
        callback = telegram_worker.create_telegram_worker_callback()
        
        with patch('urllib.request.urlopen') as mock_urlopen:
            with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "T", "TELEGRAM_CHAT_ID": "C"}):
                callback(task)
                # Should discard due to old generation without calling network
                mock_urlopen.assert_not_called()

if __name__ == '__main__':
    unittest.main()

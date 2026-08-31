import unittest
import json
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app
import db
import state
import replay
import ai_worker
import telegram_worker


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeCompletions:
    def __init__(self, client):
        self.client = client

    def create(self, **kwargs):
        client = self.client
        if client.reset_callback is not None:
            client.reset_callback()
        if client.fail_next:
            client.fail_next = False
            raise Exception("Mock Groq timeout")
        return client.mock_response


class FakeChat:
    def __init__(self, client):
        self.completions = FakeCompletions(client)


class FakeGroqClient:
    def __init__(self):
        self.chat = FakeChat(self)
        self.mock_response = None
        self.fail_next = False
        self.reset_callback = None

    def set_response(self, result_dict):
        content = json.dumps(result_dict)
        self.mock_response = type('obj', (object,), {'choices': [FakeChoice(content)]})


class MockResponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


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


class TestStability(unittest.TestCase):

    def setUp(self):
        if app._ai_thread and app._ai_thread.is_alive():
            app.ai_queue.put(None)
            app._ai_thread.join(timeout=2)
        if app._telegram_thread and app._telegram_thread.is_alive():
            app.telegram_queue.put(None)
            app._telegram_thread.join(timeout=2)
        app._worker_started = False
        app._ai_thread = None
        app._telegram_thread = None

        while not app.ai_queue.empty():
            app.ai_queue.get()
        while not app.telegram_queue.empty():
            app.telegram_queue.get()

        telegram_worker.reset_deduplication()

        self.db_fd, self.db_path = tempfile.mkstemp()
        db.DEFAULT_DB_PATH = self.db_path
        db.init_db(self.db_path)
        state.reset_state()

        app.app.config['TESTING'] = True
        self.client = app.app.test_client()

        self.critical_result = {
            "event_type": "Privilege Escalation",
            "source": "10.0.0.99",
            "target_service": "Admin System",
            "timestamp": "2026-08-23T10:15:00Z",
            "attempt_count": 5,
            "previous_related_events": ["10.0.0.99 Port Scan at Web Service"],
            "current_risk_context": {"risk_score": 48, "stage": "Access Attempt"},
            "severity": "CRITICAL",
            "risk_score": 91,
            "stage": "Escalation",
            "executive_title": "Critical Intrusion",
            "executive_summary": "Escalation observed from a single origin",
            "business_impact": "High",
            "recommended_action": "Isolate immediately",
            "telegram_alert": "CRITICAL: intrusion observed from 10.0.0.99"
        }

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _benign_event(self, source="10.0.0.1", timestamp="2026-08-23T09:00:00Z"):
        return {
            "event_type": "Login Attempt",
            "source": source,
            "target_service": "Web Service",
            "timestamp": timestamp,
            "attempt_count": 1,
            "previous_related_events": [],
            "current_risk_context": {"risk_score": 0, "stage": "Discovery"}
        }

    def _drain_ai_tasks(self):
        tasks = []
        while not app.ai_queue.empty():
            tasks.append(app.ai_queue.get())
        return tasks

    def _build_critical_scenario(self):
        self.client.post('/demo/replay/1')
        self.client.post('/demo/replay/2')
        resp3 = self.client.post('/demo/replay/3')
        snap = state.get_snapshot()
        self.assertEqual(snap["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(snap["current_risk"], 91)
        return resp3

    def test_1_event_ingestion(self):
        broadcasts = []
        payload = self._benign_event()
        with patch('app.broadcast_message', side_effect=lambda kind, payload: broadcasts.append((kind, payload))):
            resp = self.client.post('/webhook/opencanary', json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["accepted"])
        self.assertIn("event_id", data)

        events = db.get_events(self.db_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], payload["source"])
        self.assertEqual(events[0]["risk"], 21)

        snap = state.get_snapshot()
        self.assertEqual(snap["current_risk"], 21)
        self.assertEqual(snap["current_state"], state.UNDER_OBSERVATION)
        self.assertIn("Discovery", snap["timeline"])

        kinds = [k for k, _ in broadcasts]
        self.assertIn("EVENT", kinds)
        self.assertIn("STATE", kinds)

        self.assertFalse(app.ai_queue.empty())
        task = app.ai_queue.get()
        self.assertEqual(task["event_id"], events[0]["event_id"])
        self.assertEqual(task["generation"], snap["generation"])
        self.assertIn("normalized_event", task)

    def test_2_groq_delay_keeps_dashboard_risk_timeline_sqlite(self):
        self.client.post('/demo/replay/1')
        snap_before = state.get_snapshot()
        events_before = db.get_events(self.db_path)
        self.assertEqual(snap_before["current_risk"], 21)

        task = app.ai_queue.get()
        self.assertEqual(task["event_id"], events_before[0]["event_id"])

        fake = FakeGroqClient()
        fake.fail_next = True
        broadcasts = []
        ai_worker.process_ai_task(task, fake, app.telegram_queue, lambda k, p: broadcasts.append((k, p)))

        snap_after = state.get_snapshot()
        self.assertIsNone(snap_after["ai_result"])
        self.assertEqual(snap_after["current_risk"], snap_before["current_risk"])
        self.assertEqual(snap_after["current_state"], snap_before["current_state"])
        self.assertEqual(snap_after["timeline"], snap_before["timeline"])

        events_after = db.get_events(self.db_path)
        self.assertEqual(len(events_after), 1)
        self.assertEqual(events_after[0]["risk"], 21)
        self.assertIsNone(events_after[0]["ai_classification"])

        self.assertEqual([k for k, _ in broadcasts], [])

    def test_3_telegram_failure_isolation_during_critical(self):
        self._build_critical_scenario()
        snap_before = state.get_snapshot()
        self.assertEqual(len(db.get_events(self.db_path)), 3)
        self.assertEqual(snap_before["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(snap_before["current_risk"], 91)

        tasks = self._drain_ai_tasks()
        self.assertEqual(len(tasks), 3)
        event3_task = tasks[-1]

        fake = FakeGroqClient()
        fake.set_response(self.critical_result)
        ai_worker.process_ai_task(event3_task, fake, app.telegram_queue, lambda k, p: None)

        snap = state.get_snapshot()
        self.assertIsNotNone(snap["ai_result"])
        self.assertEqual(snap["ai_result"]["severity"], "CRITICAL")
        self.assertFalse(app.telegram_queue.empty())
        tel_task = app.telegram_queue.get()
        self.assertEqual(tel_task["event_id"], event3_task["event_id"])

        opener = MockOpener()
        opener.fail_next = Exception("Telegram transport down")
        tel_cb = telegram_worker.create_telegram_worker_callback(opener=opener)
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_CHAT_ID": "chat"}, clear=True):
            tel_cb(tel_task)

        self.assertEqual(len(opener.requests), 1)
        snap_after = state.get_snapshot()
        self.assertEqual(snap_after["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(snap_after["current_risk"], 91)
        self.assertIsNotNone(snap_after["ai_result"])
        self.assertEqual(len(db.get_events(self.db_path)), 3)

    def test_4_browser_reload_restores_critical_state(self):
        self._build_critical_scenario()
        snap = state.get_snapshot()
        self.assertEqual(snap["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(snap["current_risk"], 91)
        self.assertIn("Escalation", snap["timeline"])

        resp = self.client.get('/events')
        self.assertEqual(resp.status_code, 200)
        generator = resp.response
        first_frame = next(generator)
        if isinstance(first_frame, bytes):
            first_frame = first_frame.decode('utf-8')
        self.assertTrue(first_frame.startswith("data: "))
        data_json = json.loads(first_frame[6:-2])
        self.assertEqual(data_json["kind"], "STATE")
        init = data_json["payload"]
        self.assertEqual(init["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(init["current_risk"], 91)
        self.assertEqual(init["timeline"], snap["timeline"])
        self.assertIsNotNone(init.get("current_source"))
        self.assertIsNotNone(init.get("current_stage"))
        generator.close()

    def test_5_reset_during_ai_ignores_old_result(self):
        self.client.post('/webhook/opencanary', json=self._benign_event())
        old_task = app.ai_queue.get()
        old_gen = old_task["generation"]

        fake = FakeGroqClient()
        fake.set_response(self.critical_result)
        fake.reset_callback = lambda: self.client.post('/demo/reset')

        broadcasts = []
        ai_worker.process_ai_task(old_task, fake, app.telegram_queue, lambda k, p: broadcasts.append((k, p)))

        snap = state.get_snapshot()
        self.assertIsNone(snap["ai_result"])
        self.assertNotEqual(snap["generation"], old_gen)
        self.assertEqual(snap["current_risk"], 0)
        self.assertEqual(snap["current_state"], state.NORMAL)
        self.assertEqual(snap["timeline"], [])
        self.assertEqual([k for k, _ in broadcasts], [])
        self.assertTrue(app.telegram_queue.empty())

        self.client.post('/webhook/opencanary', json=self._benign_event())
        events = db.get_events(self.db_path)
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0]["ai_classification"])
        new_snap = state.get_snapshot()
        self.assertEqual(new_snap["generation"], snap["generation"])
        self.assertEqual(new_snap["current_risk"], 21)
        self.assertEqual(new_snap["current_state"], state.UNDER_OBSERVATION)

    def test_6_replay_sequence_progression(self):
        broadcasts = []
        with patch('app.broadcast_message', side_effect=lambda kind, payload: broadcasts.append((kind, payload))):
            self.client.post('/demo/replay/1')
        snap = state.get_snapshot()
        self.assertEqual(snap["current_risk"], 21)
        self.assertEqual(snap["current_state"], state.UNDER_OBSERVATION)
        self.assertIn("Discovery", snap["timeline"])

        with patch('app.broadcast_message', side_effect=lambda kind, payload: broadcasts.append((kind, payload))):
            self.client.post('/demo/replay/2')
        snap = state.get_snapshot()
        self.assertEqual(snap["current_risk"], 48)
        self.assertEqual(snap["current_state"], state.UNDER_OBSERVATION)
        self.assertIn("Service Probe", snap["timeline"])

        with patch('app.broadcast_message', side_effect=lambda kind, payload: broadcasts.append((kind, payload))):
            self.client.post('/demo/replay/3')
        snap = state.get_snapshot()
        self.assertEqual(snap["current_risk"], 91)
        self.assertEqual(snap["current_state"], state.CRITICAL_INTRUSION)
        for stage in ["Discovery", "Service Probe", "Access Attempt", "Escalation"]:
            self.assertIn(stage, snap["timeline"])

        kinds = [k for k, _ in broadcasts]
        self.assertIn("EVENT", kinds)
        self.assertIn("STATE", kinds)
        self.assertEqual(len(db.get_events(self.db_path)), 3)

    def test_6_replay_route_invokes_same_ingest_pipeline_as_live(self):
        ev3 = replay.get_replay_event(3)
        with patch('app.ingest_event', return_value={"status": "success", "event_id": 1, "accepted": True}) as mock_ingest:
            resp = self.client.post('/demo/replay/3')
            self.assertEqual(resp.status_code, 200)
            mock_ingest.assert_called_once_with(ev3)

    def test_7_crime_scene_evidence_comes_from_sqlite(self):
        replay_events = replay.load_replay_events()
        expected_origin = replay_events[0]["source"]
        expected_first_seen = replay_events[0]["timestamp"]
        expected_first_target = replay_events[0]["target_service"]

        self.client.post('/demo/replay/1')
        self.client.post('/demo/replay/2')
        self.client.post('/demo/replay/3')
        self.client.post('/contain')
        self.assertEqual(state.get_snapshot()["current_state"], state.CONTAINED)

        resp = self.client.post('/crime-scene')
        self.assertEqual(resp.status_code, 200)
        evidence = resp.get_json()

        db_events = db.get_events(self.db_path)
        self.assertEqual(evidence["Evidence 01 - First Seen"], expected_first_seen)
        self.assertEqual(evidence["Evidence 02 - Origin"], expected_origin)
        self.assertEqual(evidence["Evidence 03 - First Target"], expected_first_target)
        self.assertEqual(evidence["Evidence 04 - Activity Sequence"], [e["service"] for e in db_events])
        self.assertEqual(evidence["Evidence 05 - Critical Transition"], replay_events[2]["event_type"])
        self.assertEqual(state.get_snapshot()["current_state"], state.FORENSIC)

    def test_8_final_reset_clears_full_scenario(self):
        self.client.post('/demo/replay/1')
        self.client.post('/demo/replay/2')
        self.client.post('/demo/replay/3')

        tasks = self._drain_ai_tasks()
        event3_task = tasks[-1]
        fake = FakeGroqClient()
        fake.set_response(self.critical_result)
        ai_worker.process_ai_task(event3_task, fake, app.telegram_queue, lambda k, p: None)

        snap = state.get_snapshot()
        self.assertEqual(snap["current_state"], state.CRITICAL_INTRUSION)
        self.assertIsNotNone(snap["ai_result"])

        self.client.post('/contain')
        self.client.post('/crime-scene')

        gen_before = state.get_generation()
        with patch('telegram_worker.reset_deduplication') as mock_dedup_reset:
            resp = self.client.post('/demo/reset')
            self.assertEqual(resp.status_code, 200)
            mock_dedup_reset.assert_called_once()

        snap = state.get_snapshot()
        self.assertEqual(snap["current_risk"], 0)
        self.assertEqual(snap["current_state"], state.NORMAL)
        self.assertEqual(snap["timeline"], [])
        self.assertIsNone(snap["ai_result"])
        self.assertEqual(len(db.get_events(self.db_path)), 0)
        self.assertGreater(snap["generation"], gen_before)


if __name__ == '__main__':
    unittest.main()

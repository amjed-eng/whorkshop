import unittest
import json
import tempfile
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app
import db
import state
import opencanary_adapter

TOKEN = "test-secret-token-abc"


def native_payload(logtype=5001, src="203.0.113.77", port="22"):
    return {
        "message": json.dumps(
            {
                "src_host": src,
                "src_port": "53000",
                "dst_host": "192.0.2.50",
                "dst_port": port,
                "logtype": logtype,
                "logdata": {},
                "node_id": "canary-1",
                "utc_time": "2026-08-23 10:00:00.000000",
                "local_time": "2026-08-23 10:00:00.000000",
            }
        )
    }


def canonical_admin_payload(src="203.0.113.88"):
    return {
        "event_type": "Login",
        "source": src,
        "target_service": "Admin System",
        "timestamp": "2026-08-23T11:00:00Z",
        "attempt_count": 1,
        "previous_related_events": [],
        "current_risk_context": {"risk_score": 0, "stage": "initial"},
    }


class NativeWebhookBase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        db.DEFAULT_DB_PATH = self.db_path
        db.init_db(self.db_path)
        state.reset_state()
        opencanary_adapter.reset_correlation()
        app.app.config["TESTING"] = True
        self.client = app.app.test_client()
        self._drain(app.ai_queue)
        self._drain(app.telegram_queue)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    @staticmethod
    def _drain(queue):
        while not queue.empty():
            queue.get()


class TestNativeStateIntegration(NativeWebhookBase):
    def test_first_native_port_scan_reaches_observation_risk_48(self):
        resp = self.client.post("/webhook/opencanary-native", json=native_payload())
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["accepted"])
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["current_state"], state.UNDER_OBSERVATION)
        self.assertEqual(snapshot["current_risk"], 48)
        self.assertEqual(snapshot["current_stage"], "Service Probe")

    def test_repeated_scan_from_same_source_correlates(self):
        for _ in range(3):
            resp = self.client.post("/webhook/opencanary-native", json=native_payload())
            self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            opencanary_adapter.source_correlation("203.0.113.77")["attempt_count"], 3
        )
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["event_count"], 3)
        self.assertEqual(snapshot["current_risk"], 48)
        self.assertEqual(snapshot["current_state"], state.UNDER_OBSERVATION)

    def test_multiple_target_services_tracked(self):
        for port in ("22", "80", "443"):
            resp = self.client.post(
                "/webhook/opencanary-native", json=native_payload(port=port)
            )
            self.assertEqual(resp.status_code, 200)
        corr = opencanary_adapter.source_correlation("203.0.113.77")
        self.assertEqual(corr["services"], ["HTTP", "HTTPS", "SSH"])
        self.assertEqual(state.get_snapshot()["event_count"], 3)

    def test_scan_does_not_directly_call_groq(self):
        with patch("ai_worker.Groq") as mock_groq, patch(
            "urllib.request.urlopen"
        ) as mock_urlopen:
            resp = self.client.post(
                "/webhook/opencanary-native", json=native_payload()
            )
            self.assertEqual(resp.status_code, 200)
            mock_groq.assert_not_called()
            mock_urlopen.assert_not_called()
        self.assertFalse(app.ai_queue.empty())

    def test_scan_does_not_directly_call_telegram(self):
        import telegram_worker
        with patch("telegram_worker.send_telegram_message") as mock_send:
            resp = self.client.post(
                "/webhook/opencanary-native", json=native_payload()
            )
            self.assertEqual(resp.status_code, 200)
            mock_send.assert_not_called()
        self.assertTrue(app.telegram_queue.empty())


class TestCriticalEscalation(NativeWebhookBase):
    def test_scan_then_sensitive_admin_activity_reaches_91(self):
        self.client.post("/webhook/opencanary-native", json=native_payload())
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["current_risk"], 48)
        self.assertEqual(snapshot["current_state"], state.UNDER_OBSERVATION)

        resp = self.client.post(
            "/webhook/opencanary", json=canonical_admin_payload()
        )
        self.assertEqual(resp.status_code, 200)
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(snapshot["current_risk"], 91)
        self.assertEqual(snapshot["current_stage"], "Escalation")

    def test_generic_repeated_benign_activity_not_critical_by_count(self):
        src = "198.51.100.90"
        for _ in range(51):
            resp = self.client.post(
                "/webhook/opencanary-native",
                json=native_payload(logtype=3000, port="80", src=src),
            )
            self.assertEqual(resp.status_code, 200)
        snapshot = state.get_snapshot()
        self.assertNotEqual(snapshot["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(snapshot["current_state"], state.UNDER_OBSERVATION)
        self.assertEqual(snapshot["current_risk"], 48)

    def test_critical_state_not_downgraded_by_benign_later_event(self):
        self.client.post("/webhook/opencanary", json=canonical_admin_payload())
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(snapshot["current_risk"], 91)

        resp = self.client.post(
            "/webhook/opencanary-native",
            json=native_payload(logtype=3000, port="80", src="203.0.113.5"),
        )
        self.assertEqual(resp.status_code, 200)
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(snapshot["current_risk"], 91)
        self.assertEqual(snapshot["current_stage"], "Escalation")


class TestNativePipeline(NativeWebhookBase):
    def test_native_route_invokes_same_ingest_event(self):
        payload = native_payload()
        with patch(
            "app.ingest_event",
            return_value={"status": "success", "event_id": 1},
        ) as mock_ingest:
            resp = self.client.post("/webhook/opencanary-native", json=payload)
            self.assertEqual(resp.status_code, 200)
            mock_ingest.assert_called_once()
            call = mock_ingest.call_args
            canonical = call[0][0]
            kwargs = call[1]
        self.assertEqual(kwargs["evidence_source"], payload)
        self.assertEqual(canonical["event_type"], "Port Scan")
        self.assertEqual(canonical["source"], "203.0.113.77")
        self.assertEqual(canonical["target_service"], "SSH")
        self.assertIn("timestamp", canonical)
        self.assertIn("attempt_count", canonical)
        self.assertIn("current_risk_context", canonical)
        self.assertNotIn("logtype", canonical)

    def test_sqlite_evidence_created(self):
        resp = self.client.post("/webhook/opencanary-native", json=native_payload())
        self.assertEqual(resp.status_code, 200)
        events = db.get_events(self.db_path)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], "203.0.113.77")
        self.assertEqual(events[0]["service"], "SSH")
        self.assertEqual(events[0]["event_type"], "Port Scan")
        self.assertEqual(events[0]["risk"], 48)

    def test_sse_event_and_state_emitted(self):
        with patch("app.broadcast_message") as mock_broadcast:
            resp = self.client.post(
                "/webhook/opencanary-native", json=native_payload()
            )
            self.assertEqual(resp.status_code, 200)
            kinds = [call_args[0][0] for call_args in mock_broadcast.call_args_list]
            self.assertIn("EVENT", kinds)
            self.assertIn("STATE", kinds)
            event_call = [
                call_args
                for call_args in mock_broadcast.call_args_list
                if call_args[0][0] == "EVENT"
            ][0]
            normalized = event_call[0][1]["normalized"]
            self.assertEqual(normalized["event_type"], "Port Scan")
            self.assertEqual(normalized["target_service"], "SSH")

    def test_ai_queue_receives_canonical_task_with_raw_hash(self):
        payload = native_payload()
        resp = self.client.post("/webhook/opencanary-native", json=payload)
        self.assertEqual(resp.status_code, 200)
        task = app.ai_queue.get()
        normalized = task["normalized_event"]
        self.assertEqual(normalized["event_type"], "Port Scan")
        self.assertEqual(normalized["source"], "203.0.113.77")
        self.assertEqual(normalized["target_service"], "SSH")
        self.assertNotIn("logtype", normalized)
        self.assertEqual(task["raw_event_hash"], app.generate_hash(payload))

    def test_no_raw_payload_in_sse(self):
        payload = native_payload()
        with patch("app.broadcast_message") as mock_broadcast:
            resp = self.client.post("/webhook/opencanary-native", json=payload)
            self.assertEqual(resp.status_code, 200)
            for call_args in mock_broadcast.call_args_list:
                body_text = json.dumps(call_args[0][1])
                self.assertNotIn("logtype", body_text)
                self.assertNotIn("dst_host", body_text)
                self.assertNotIn("node_id", body_text)
                self.assertNotIn("src_host", body_text)

    def test_malformed_event_creates_no_evidence(self):
        bad_payloads = [
            {"message": "not valid json"},
            {
                "logtype": 5001,
                "dst_port": "22",
                "dst_host": "192.0.2.50",
                "utc_time": "2026-08-23 10:00:00.000000",
            },
            {"message": 123},
        ]
        for payload in bad_payloads:
            with self.subTest(payload=payload):
                resp = self.client.post("/webhook/opencanary-native", json=payload)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(len(db.get_events(self.db_path)), 0)
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["current_risk"], 0)
        self.assertEqual(snapshot["current_state"], state.NORMAL)

    def test_malformed_event_creates_no_ai_task(self):
        self._drain(app.ai_queue)
        for payload in [{"message": "not valid json"}, {"logtype": 5001}]:
            resp = self.client.post("/webhook/opencanary-native", json=payload)
            self.assertEqual(resp.status_code, 400)
        self.assertTrue(app.ai_queue.empty())

    def test_not_json_body_rejected(self):
        resp = self.client.post(
            "/webhook/opencanary-native",
            data="message=hello",
            content_type="application/x-www-form-urlencoded",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(db.get_events(self.db_path)), 0)

    def test_payload_size_limit_enforced(self):
        original = app.MAX_NATIVE_PAYLOAD_BYTES
        app.MAX_NATIVE_PAYLOAD_BYTES = 10
        try:
            resp = self.client.post(
                "/webhook/opencanary-native", json=native_payload()
            )
            self.assertEqual(resp.status_code, 400)
            self.assertEqual(len(db.get_events(self.db_path)), 0)
        finally:
            app.MAX_NATIVE_PAYLOAD_BYTES = original


class TestNativeSecurity(NativeWebhookBase):
    def test_correct_webhook_token_accepted(self):
        with patch_env(TOKEN):
            resp = self.client.post(
                "/webhook/opencanary-native",
                json=native_payload(),
                headers={"X-OpenCanary-Token": TOKEN},
            )
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(len(db.get_events(self.db_path)), 1)

    def test_incorrect_token_rejected(self):
        with patch_env(TOKEN):
            resp = self.client.post(
                "/webhook/opencanary-native",
                json=native_payload(),
                headers={"X-OpenCanary-Token": "wrong-secret"},
            )
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(len(db.get_events(self.db_path)), 0)

    def test_secret_does_not_appear_in_response(self):
        with patch_env(TOKEN):
            cases = [
                {"X-OpenCanary-Token": TOKEN},
                {"X-OpenCanary-Token": "wrong-secret"},
                {},
            ]
            for headers in cases:
                with self.subTest(headers=headers):
                    resp = self.client.post(
                        "/webhook/opencanary-native",
                        json=native_payload(),
                        headers=headers,
                    )
                    self.assertNotIn(TOKEN, resp.get_data(as_text=True))

    def test_secret_does_not_appear_in_sse(self):
        with patch("app.broadcast_message") as mock_broadcast, patch_env(TOKEN):
            resp = self.client.post(
                "/webhook/opencanary-native",
                json=native_payload(),
                headers={"X-OpenCanary-Token": TOKEN},
            )
            self.assertEqual(resp.status_code, 200)
            for call_args in mock_broadcast.call_args_list:
                self.assertNotIn(TOKEN, json.dumps(call_args[0][1]))

    def test_missing_configured_token_rejected(self):
        with patch_env(TOKEN):
            resp = self.client.post("/webhook/opencanary-native", json=native_payload())
            self.assertEqual(resp.status_code, 401)
            self.assertEqual(len(db.get_events(self.db_path)), 0)
            resp = self.client.post(
                "/webhook/opencanary-native",
                json=native_payload(),
                headers={"X-OpenCanary-Token": ""},
            )
            self.assertEqual(resp.status_code, 401)

    def test_development_mode_open_when_token_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            resp = self.client.post(
                "/webhook/opencanary-native", json=native_payload()
            )
            self.assertEqual(resp.status_code, 200)


def patch_env(token):
    return patch.dict(os.environ, {"OPENCANARY_WEBHOOK_TOKEN": token})


if __name__ == "__main__":
    unittest.main()

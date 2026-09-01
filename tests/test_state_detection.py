import unittest

import state


class TestStateDetectionSignals(unittest.TestCase):
    def setUp(self):
        state.reset_state()

    def test_first_nmap_scan_is_observed_at_probe_risk(self):
        result = state.process_event({
            "source": "203.0.113.10",
            "target_service": "Web Service",
            "event_type": "Nmap SYN Scan",
            "attempt_count": 64,
            "previous_related_events": [],
            "current_risk_context": {"risk_score": 0, "stage": "Discovery"},
        })
        snapshot = state.get_snapshot()
        self.assertEqual(result["state"], state.UNDER_OBSERVATION)
        self.assertEqual(result["risk"], 48)
        self.assertEqual(snapshot["current_stage"], "Service Probe")
        self.assertIn("Discovery", snapshot["timeline"])
        self.assertIn("Service Probe", snapshot["timeline"])

    def test_high_volume_unknown_activity_is_suspicious_not_automatically_critical(self):
        result = state.process_event({
            "source": "203.0.113.11",
            "target_service": "Web Service",
            "event_type": "Vendor Specific Network Activity",
            "attempt_count": 25,
            "previous_related_events": [],
            "current_risk_context": {"risk_score": 10, "stage": "Discovery"},
        })
        self.assertEqual(result["state"], state.UNDER_OBSERVATION)
        self.assertEqual(result["risk"], 48)

    def test_correlated_high_volume_high_context_event_can_escalate_without_keyword(self):
        result = state.process_event({
            "source": "203.0.113.12",
            "target_service": "Web Service",
            "event_type": "Vendor Event 9001",
            "attempt_count": 80,
            "previous_related_events": ["related observation"],
            "current_risk_context": {"risk_score": 85, "stage": "Access Attempt"},
        })
        self.assertEqual(result["state"], state.CRITICAL_INTRUSION)
        self.assertEqual(result["risk"], 91)

    def test_new_benign_source_cannot_lower_existing_critical_risk(self):
        state.process_event({
            "source": "198.51.100.1",
            "target_service": "Admin System",
            "event_type": "Login",
        })
        state.process_event({
            "source": "198.51.100.2",
            "target_service": "HTTP",
            "event_type": "GET",
        })
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["current_state"], state.CRITICAL_INTRUSION)
        self.assertEqual(snapshot["current_risk"], 91)
        self.assertEqual(snapshot["current_stage"], "Escalation")

    def test_snapshot_tracks_total_events_and_most_targeted_asset(self):
        state.process_event({"source": "a", "target_service": "Web Service", "event_type": "GET"})
        state.process_event({"source": "b", "target_service": "Admin System", "event_type": "GET"})
        state.process_event({"source": "c", "target_service": "Web Service", "event_type": "GET"})
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot["event_count"], 3)
        self.assertEqual(snapshot["most_targeted_asset"], "Web Service")


if __name__ == "__main__":
    unittest.main()

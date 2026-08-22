import unittest
import state

class TestState(unittest.TestCase):
    def setUp(self):
        # Reset state before each test to ensure clean testing environment
        # But we need to save the generation so we can track it
        # Actually reset_state increments generation, which is fine.
        state.reset_state()

    def test_initial_state(self):
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot['current_state'], state.NORMAL)
        self.assertEqual(snapshot['current_risk'], 0)
        self.assertIsNone(snapshot['current_stage'])
        self.assertIsNone(snapshot['current_source'])
        self.assertEqual(snapshot['timeline'], [])
        self.assertGreaterEqual(snapshot['generation'], 1)

    def test_event_progression(self):
        # Event 1
        res = state.process_event({"source": "10.0.0.1", "target_service": "SSH", "event_type": "Login Attempt"})
        self.assertEqual(res['risk'], 21)
        self.assertEqual(res['state'], state.UNDER_OBSERVATION)
        snapshot = state.get_snapshot()
        self.assertIn("Discovery", snapshot['timeline'])
        
        # Event 2 same source
        res = state.process_event({"source": "10.0.0.1", "target_service": "HTTP", "event_type": "GET"})
        self.assertEqual(res['risk'], 48)
        self.assertEqual(res['state'], state.UNDER_OBSERVATION)
        snapshot = state.get_snapshot()
        self.assertIn("Service Probe", snapshot['timeline'])
        
        # Event 3 same source but BENIGN (Data Read is not intrinsically critical in our generic list unless marked escalation)
        res = state.process_event({"source": "10.0.0.1", "target_service": "MySQL", "event_type": "Data Read"})
        self.assertEqual(res['risk'], 48)
        self.assertEqual(res['state'], state.UNDER_OBSERVATION)

    def test_update_risk_invalid(self):
        with self.assertRaises(ValueError):
            state.update_risk(-1)
        with self.assertRaises(ValueError):
            state.update_risk(101)
        with self.assertRaises(ValueError):
            state.update_risk("high")

    def test_transition_state_invalid(self):
        with self.assertRaises(ValueError):
            state.transition_state("UNKNOWN_STATE")

    def test_containment_does_not_duplicate_timeline(self):
        state.contain_threat()
        state.contain_threat()
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot['timeline'].count("Containment"), 1)

    def test_reset_clears_counters_and_ai(self):
        state.apply_ai_result({"severity": "HIGH"}, state.get_generation())
        state.reset_state()
        snapshot = state.get_snapshot()
        self.assertIsNone(snapshot['ai_result'])
        self.assertEqual(snapshot['current_risk'], 0)

    def test_ai_cannot_downgrade_critical(self):
        res = state.process_event({"source": "192.168.1.50", "target_service": "Admin System", "event_type": "Login"})
        self.assertEqual(res['state'], state.CRITICAL_INTRUSION)
        
        # AI says benign
        state.apply_ai_result({"severity": "LOW", "risk_score": 10}, state.get_generation())
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot['current_state'], state.CRITICAL_INTRUSION)
        self.assertEqual(snapshot['current_risk'], 91)

    def test_sensitive_event(self):
        res = state.process_event({"source": "192.168.1.50", "target_service": "Admin System", "event_type": "Login"})
        self.assertEqual(res['risk'], 91)
        self.assertEqual(res['state'], state.CRITICAL_INTRUSION)
        snapshot = state.get_snapshot()
        self.assertIn("Escalation", snapshot['timeline'])

    def test_containment(self):
        state.contain_threat()
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot['current_state'], state.CONTAINED)
        self.assertIn("Containment", snapshot['timeline'])

    def test_modes(self):
        state.enter_forensic_mode()
        self.assertEqual(state.get_snapshot()['current_state'], state.FORENSIC)
        
        state.enter_executive_mode()
        self.assertEqual(state.get_snapshot()['current_state'], state.EXECUTIVE)

    def test_reset_increments_generation(self):
        gen1 = state.get_generation()
        state.reset_state()
        gen2 = state.get_generation()
        self.assertGreater(gen2, gen1)

    def test_old_ai_result_rejected(self):
        gen = state.get_generation()
        state.reset_state() # gen increments
        
        # Try to apply result for old gen
        accepted = state.apply_ai_result({"severity": "CRITICAL", "risk_score": 90}, gen)
        self.assertFalse(accepted)
        
        snapshot = state.get_snapshot()
        self.assertIsNone(snapshot['ai_result'])

    def test_valid_ai_result_accepted(self):
        gen = state.get_generation()
        ai_data = {"severity": "HIGH", "risk_score": 70}
        accepted = state.apply_ai_result(ai_data, gen)
        self.assertTrue(accepted)
        
        snapshot = state.get_snapshot()
        self.assertEqual(snapshot['ai_result'], ai_data)

    def test_get_snapshot_mutation(self):
        snapshot1 = state.get_snapshot()
        snapshot1['timeline'].append("Fake Event")
        
        snapshot2 = state.get_snapshot()
        self.assertNotIn("Fake Event", snapshot2['timeline'])

if __name__ == '__main__':
    unittest.main()

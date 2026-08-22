import unittest
import tempfile
import os
import json
from db import init_db, save_event, update_event_risk, update_ai_classification, get_events, reset_demo

class TestDB(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        init_db(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_production_db_isolation(self):
        prod_db = "data/evidence.sqlite3"
        initial_mtime = None
        if os.path.exists(prod_db):
            initial_mtime = os.path.getmtime(prod_db)
            
        import db
        # Force a generic write using default args which should resolve to db.DEFAULT_DB_PATH
        # But we mock it! Wait, we actually want to ensure db.DEFAULT_DB_PATH isolation.
        db.DEFAULT_DB_PATH = self.db_path
        db.init_db()
        db.save_event("t", "10.0.0.1", "SSH", "Login", "hash", risk=10)
        
        if initial_mtime is None:
            self.assertFalse(os.path.exists(prod_db), "Production DB was created during tests!")
        else:
            self.assertEqual(os.path.getmtime(prod_db), initial_mtime, "Production DB was modified during tests!")

    def test_init_db_creates_table(self):
        # Already called in setUp, testing if we can write to it
        rowid = save_event('2026-08-23T00:00:00Z', '192.168.1.100', 'SSH', 'Login Attempt', 'hash123', risk=10, db_path=self.db_path)
        self.assertEqual(rowid, 1)

    def test_save_and_get_events(self):
        save_event('2026-08-23T00:01:00Z', '10.0.0.1', 'FTP', 'Connection', 'hash1', risk=0, db_path=self.db_path)
        save_event('2026-08-23T00:02:00Z', '10.0.0.2', 'HTTP', 'GET', 'hash2', risk=5, db_path=self.db_path)
        
        events = get_events(self.db_path)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['event_id'], 1)
        self.assertEqual(events[0]['source'], '10.0.0.1')
        self.assertEqual(events[1]['event_id'], 2)
        self.assertEqual(events[1]['service'], 'HTTP')

    def test_update_event_risk(self):
        rowid = save_event('2026-08-23T00:00:00Z', '192.168.1.100', 'SSH', 'Login Attempt', 'hash123', risk=10, db_path=self.db_path)
        update_event_risk(rowid, 45, db_path=self.db_path)
        
        events = get_events(self.db_path)
        self.assertEqual(events[0]['risk'], 45)

    def test_update_event_risk_invalid(self):
        rowid = save_event('2026-08-23T00:00:00Z', '192.168.1.100', 'SSH', 'Login Attempt', 'hash123', risk=10, db_path=self.db_path)
        with self.assertRaises(ValueError):
            update_event_risk(rowid, 150, db_path=self.db_path)
        with self.assertRaises(ValueError):
            update_event_risk(rowid, -5, db_path=self.db_path)
        with self.assertRaises(ValueError):
            update_event_risk(rowid, "high", db_path=self.db_path)

    def test_update_ai_classification(self):
        rowid = save_event('2026-08-23T00:00:00Z', '192.168.1.100', 'SSH', 'Login Attempt', 'hash123', risk=10, db_path=self.db_path)
        ai_data = {"severity": "CRITICAL", "risk_score": 90}
        update_ai_classification(rowid, ai_data, 90, db_path=self.db_path)
        
        events = get_events(self.db_path)
        self.assertEqual(events[0]['risk'], 90)
        self.assertEqual(json.loads(events[0]['ai_classification']), ai_data)

    def test_reset_demo(self):
        save_event('2026-08-23T00:00:00Z', '192.168.1.100', 'SSH', 'Login Attempt', 'hash123', risk=10, db_path=self.db_path)
        save_event('2026-08-23T00:01:00Z', '10.0.0.1', 'FTP', 'Connection', 'hash1', risk=0, db_path=self.db_path)
        
        self.assertEqual(len(get_events(self.db_path)), 2)
        reset_demo(self.db_path)
        self.assertEqual(len(get_events(self.db_path)), 0)

    def test_ordering(self):
        # Even if saved out of order, they should be returned ordered by timestamp ASC, rowid ASC
        save_event('2026-08-23T00:02:00Z', '10.0.0.2', 'HTTP', 'GET', 'h2', db_path=self.db_path)
        save_event('2026-08-23T00:01:00Z', '10.0.0.1', 'FTP', 'Connection', 'h1', db_path=self.db_path)
        
        events = get_events(self.db_path)
        self.assertEqual(events[0]['source'], '10.0.0.1')
        self.assertEqual(events[1]['source'], '10.0.0.2')

    def test_update_ai_classification_invalid_risk(self):
        rowid = save_event('2026-08-23T00:00:00Z', '192.168.1.100', 'SSH', 'Login', 'h', db_path=self.db_path)
        with self.assertRaises(ValueError):
            update_ai_classification(rowid, {}, 150, db_path=self.db_path)

if __name__ == '__main__':
    unittest.main()

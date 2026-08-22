import sqlite3
import os
import json

DEFAULT_DB_PATH = 'data/evidence.sqlite3'

def get_connection(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path=DEFAULT_DB_PATH):
    """Initialize the database and create the events table."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                service TEXT NOT NULL,
                event_type TEXT NOT NULL,
                raw_event_hash TEXT NOT NULL,
                ai_classification TEXT,
                risk INTEGER
            )
        """)
        conn.commit()
    finally:
        conn.close()

def save_event(timestamp: str, source: str, service: str, event_type: str, raw_event_hash: str, risk: int = 0, db_path=DEFAULT_DB_PATH) -> int:
    """Save an event and return its rowid."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events (timestamp, source, service, event_type, raw_event_hash, risk)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (timestamp, source, service, event_type, raw_event_hash, risk))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def update_event_risk(event_id: int, risk: int, db_path=DEFAULT_DB_PATH):
    """Update the risk of an event."""
    if not isinstance(risk, int) or risk < 0 or risk > 100:
        raise ValueError("Risk must be an integer between 0 and 100.")
    
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE events SET risk = ? WHERE rowid = ?
        """, (risk, event_id))
        conn.commit()
    finally:
        conn.close()

def update_ai_classification(event_id: int, ai_classification: dict, risk: int, db_path=DEFAULT_DB_PATH):
    """Update AI classification and risk of an event."""
    if not isinstance(risk, int) or risk < 0 or risk > 100:
        raise ValueError("Risk must be an integer between 0 and 100.")
        
    ai_classification_json = json.dumps(ai_classification, sort_keys=True, separators=(',', ':')) if isinstance(ai_classification, dict) else ai_classification
    
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE events SET ai_classification = ?, risk = ? WHERE rowid = ?
        """, (ai_classification_json, risk, event_id))
        conn.commit()
    finally:
        conn.close()

def get_events(db_path=DEFAULT_DB_PATH) -> list:
    """Retrieve all events ordered by timestamp and rowid."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rowid as event_id, timestamp, source, service, event_type, raw_event_hash, ai_classification, risk
            FROM events
            ORDER BY timestamp ASC, rowid ASC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def reset_demo(db_path=DEFAULT_DB_PATH):
    """Delete all rows from the events table without deleting the file."""
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events")
        conn.commit()
    finally:
        conn.close()

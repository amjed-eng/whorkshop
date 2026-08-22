import os
import json
import hashlib
import queue
import threading
from flask import Flask, request, jsonify, Response

import db
import state

app = Flask(__name__)

# Simple SSE Subscribers
subscribers = []
subscribers_lock = threading.Lock()

# Queue for AI tasks (used here, properly consumed in Commit 4/5)
ai_queue = queue.Queue()

# Ensure DB is initialized
db.init_db()

def broadcast_message(kind: str, payload: dict):
    message = json.dumps({"kind": kind, "payload": payload}, sort_keys=True, separators=(',', ':'))
    sse_data = f"data: {message}\n\n"
    
    with subscribers_lock:
        for q in subscribers:
            try:
                q.put_nowait(sse_data)
            except queue.Full:
                pass

def generate_hash(raw_event: dict) -> str:
    stable_json = json.dumps(raw_event, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(stable_json.encode('utf-8')).hexdigest()

def normalize_event(raw_event: dict) -> dict:
    if not isinstance(raw_event, dict):
        raise ValueError("Invalid raw event")
        
    event_type = str(raw_event.get("event_type", "")).strip()
    source = str(raw_event.get("source", "")).strip()
    target_service = str(raw_event.get("target_service", "")).strip()
    timestamp = str(raw_event.get("timestamp", "")).strip()
    attempt_count = raw_event.get("attempt_count", 1)
    
    if not event_type or not source or not target_service or not timestamp:
        raise ValueError("Missing required fields")
        
    try:
        attempt_count = int(attempt_count)
        if attempt_count < 1:
            raise ValueError
    except:
        raise ValueError("attempt_count must be an integer >= 1")
        
    previous_related = raw_event.get("previous_related_events", [])
    if not isinstance(previous_related, list):
        previous_related = []
        
    current_risk_ctx = raw_event.get("current_risk_context", {})
    if not isinstance(current_risk_ctx, dict):
        current_risk_ctx = {}
        
    if "risk_score" in current_risk_ctx:
        try:
            rs = int(current_risk_ctx["risk_score"])
            if rs < 0 or rs > 100:
                raise ValueError
        except:
            raise ValueError("risk_score must be an integer between 0 and 100")
            
    return {
        "event_type": event_type,
        "source": source,
        "target_service": target_service,
        "timestamp": timestamp,
        "attempt_count": attempt_count,
        "previous_related_events": previous_related,
        "current_risk_context": current_risk_ctx
    }

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "service": "INTRUDER_INVISIBLE",
        "status": "online",
        "current_state": state.get_snapshot()["current_state"]
    })

@app.route('/health', methods=['GET'])
def health():
    try:
        db.get_events()
        return jsonify({"status": "healthy", "db": "connected"})
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/webhook/opencanary', methods=['POST'])
def webhook_opencanary():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
        
    raw_event = request.get_json()
    
    try:
        normalized = normalize_event(raw_event)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
        
    event_hash = generate_hash(raw_event)
    
    try:
        # Save to DB first
        event_id = db.save_event(
            timestamp=normalized["timestamp"],
            source=normalized["source"],
            service=normalized["target_service"],
            event_type=normalized["event_type"],
            raw_event_hash=event_hash,
            risk=0
        )
        
        # Process locally
        local_res = state.process_event(normalized)
        
        # Update DB risk
        db.update_event_risk(event_id, local_res["risk"])
        
        # Broadcast immediate event
        broadcast_message("EVENT", {"event_id": event_id, "normalized": normalized})
        broadcast_message("STATE", state.get_snapshot())
        
        # Enqueue for AI
        gen = state.get_generation()
        ai_queue.put({
            "event_id": event_id,
            "generation": gen,
            "normalized_event": normalized,
            "raw_event_hash": event_hash
        })
        
        return jsonify({
            "accepted": True,
            "event_id": event_id,
            "generation": gen,
            "state": local_res["state"],
            "risk": local_res["risk"]
        })
        
    except Exception as e:
        app.logger.error(f"Failed to process webhook: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

@app.route('/events', methods=['GET'])
def events_stream():
    def generate():
        q = queue.Queue(maxsize=100)
        with subscribers_lock:
            subscribers.append(q)
            
        # Send initial snapshot
        init_msg = json.dumps({"kind": "STATE", "payload": state.get_snapshot()})
        yield f"data: {init_msg}\n\n"
        
        try:
            while True:
                msg = q.get(timeout=15)
                yield msg
        except queue.Empty:
            # heartbeat
            yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            with subscribers_lock:
                if q in subscribers:
                    subscribers.remove(q)

    return Response(generate(), mimetype='text/event-stream')

@app.route('/demo/reset', methods=['POST'])
def reset_demo_route():
    state.reset_state()
    db.reset_demo()
    snapshot = state.get_snapshot()
    broadcast_message("RESET", snapshot)
    return jsonify({"status": "reset", "generation": snapshot["generation"]})

@app.route('/contain', methods=['POST'])
def contain_threat_route():
    state.contain_threat()
    broadcast_message("STATE", state.get_snapshot())
    return jsonify({"status": "contained"})

@app.route('/crime-scene', methods=['POST'])
def crime_scene():
    all_events = db.get_events()
    
    first_seen = None
    origin = None
    first_target = None
    activity_sequence = []
    critical_transition = None
    
    for idx, ev in enumerate(all_events):
        if idx == 0:
            first_seen = ev["timestamp"]
            origin = ev["source"]
            first_target = ev["service"]
            
        activity_sequence.append(ev["service"])
        
        if not critical_transition:
            # Check risk > 91 or AI classification critical
            is_crit = False
            if ev["risk"] >= 91:
                is_crit = True
            elif ev["ai_classification"]:
                try:
                    ai_c = json.loads(ev["ai_classification"])
                    if ai_c.get("severity") == "CRITICAL":
                        is_crit = True
                except:
                    pass
            if is_crit:
                critical_transition = ev["event_type"]
                
    evidence = {
        "Evidence 01 - First Seen": first_seen,
        "Evidence 02 - Origin": origin,
        "Evidence 03 - First Target": first_target,
        "Evidence 04 - Activity Sequence": activity_sequence,
        "Evidence 05 - Critical Transition": critical_transition
    }
    
    state.enter_forensic_mode()
    broadcast_message("STATE", state.get_snapshot())
    
    return jsonify(evidence)

@app.route('/executive', methods=['POST'])
def executive_mode():
    state.enter_executive_mode()
    broadcast_message("STATE", state.get_snapshot())
    return jsonify({"status": "executive_mode"})

if __name__ == '__main__':
    app.run(debug=True, threaded=True)

import threading
import copy

# Allowed States
NORMAL = "NORMAL"
UNDER_OBSERVATION = "UNDER_OBSERVATION"
CRITICAL_INTRUSION = "CRITICAL_INTRUSION"
CONTAINED = "CONTAINED"
FORENSIC = "FORENSIC"
EXECUTIVE = "EXECUTIVE"

ALLOWED_STATES = {NORMAL, UNDER_OBSERVATION, CRITICAL_INTRUSION, CONTAINED, FORENSIC, EXECUTIVE}

# Shared state variables
_lock = threading.RLock()
_current_state = NORMAL
_current_risk = 0
_current_stage = None
_current_source = None
_timeline = []
_generation = 1
_ai_result = None

# Internal trackers
_event_count = 0

def _is_sensitive_event(event_type: str, service: str) -> bool:
    event_type_lower = event_type.lower()
    service_lower = service.lower()
    
    sensitive_keywords = ["admin system", "administrative system", "digital vault", "escalation", "access attempt"]
    for keyword in sensitive_keywords:
        if keyword in event_type_lower or keyword in service_lower:
            return True
    return False

def process_event(event: dict) -> dict:
    """
    Process a local event and progress state machine synchronously.
    Returns the new risk and state for convenient saving if needed.
    """
    global _current_state, _current_risk, _current_stage, _current_source, _timeline, _event_count
    
    with _lock:
        source = event.get("source", "Unknown")
        service = event.get("target_service", "")
        event_type = event.get("event_type", "")
        
        is_sensitive = _is_sensitive_event(event_type, service)
        
        # New source or starting over tracking
        if _current_source is None or _current_source != source:
            _current_source = source
            _event_count = 1
            if is_sensitive:
                update_risk(91)
                transition_state(CRITICAL_INTRUSION)
                _current_stage = "Escalation"
                _timeline = ["Discovery", "Service Probe", "Access Attempt", "Escalation"]
            else:
                update_risk(21)
                transition_state(UNDER_OBSERVATION)
                _current_stage = "Discovery"
                if "Discovery" not in _timeline:
                    _timeline.append("Discovery")
        else:
            # Same source progression
            _event_count += 1
            if is_sensitive or _event_count >= 3:
                update_risk(91)
                transition_state(CRITICAL_INTRUSION)
                _current_stage = "Escalation"
                
                # Build timeline safely without duplicates up to the progression
                for st in ["Discovery", "Service Probe", "Access Attempt", "Escalation"]:
                    if st not in _timeline:
                        _timeline.append(st)
            else:
                # 2nd event
                if _current_risk < 48:
                    update_risk(48)
                if _current_state == NORMAL:
                    transition_state(UNDER_OBSERVATION)
                _current_stage = "Service Probe"
                if "Service Probe" not in _timeline:
                    _timeline.append("Service Probe")
                    
        return {"risk": _current_risk, "state": _current_state}

def update_risk(risk: int):
    global _current_risk
    with _lock:
        if not isinstance(risk, int) or risk < 0 or risk > 100:
            raise ValueError("Risk must be an int between 0 and 100")
        _current_risk = risk

def transition_state(new_state: str):
    global _current_state
    with _lock:
        if new_state not in ALLOWED_STATES:
            raise ValueError(f"Invalid state: {new_state}")
        
        # Don't downgrade from critical directly back to observation in normal flow
        if _current_state == CRITICAL_INTRUSION and new_state in (NORMAL, UNDER_OBSERVATION):
            # Only allow reset to go to NORMAL
            if new_state != NORMAL:
                return
                
        _current_state = new_state

def reset_state():
    global _current_state, _current_risk, _current_stage, _current_source, _timeline, _generation, _ai_result, _event_count
    with _lock:
        _generation += 1
        _current_state = NORMAL
        _current_risk = 0
        _current_stage = None
        _current_source = None
        _timeline = []
        _event_count = 0
        _ai_result = None

def get_snapshot() -> dict:
    with _lock:
        return {
            "current_state": _current_state,
            "current_risk": _current_risk,
            "current_stage": _current_stage,
            "current_source": _current_source,
            "timeline": copy.deepcopy(_timeline),
            "generation": _generation,
            "ai_result": copy.deepcopy(_ai_result) if _ai_result else None
        }

def get_generation() -> int:
    with _lock:
        return _generation

def apply_ai_result(result: dict, result_generation: int) -> bool:
    global _ai_result
    with _lock:
        if result_generation != _generation:
            return False
        
        ai_severity = result.get("severity")
        if _current_state == CRITICAL_INTRUSION and ai_severity != "CRITICAL":
            # Do not allow AI to downgrade a locally determined critical state
            _ai_result = copy.deepcopy(result)
            return True
        elif ai_severity == "CRITICAL" and _current_state in (NORMAL, UNDER_OBSERVATION):
            transition_state(CRITICAL_INTRUSION)
            update_risk(max(_current_risk, result.get("risk_score", 91)))
            
        _ai_result = copy.deepcopy(result)
        return True

def contain_threat():
    global _timeline
    with _lock:
        transition_state(CONTAINED)
        if "Containment" not in _timeline:
            _timeline.append("Containment")

def enter_forensic_mode():
    with _lock:
        transition_state(FORENSIC)

def enter_executive_mode():
    with _lock:
        transition_state(EXECUTIVE)

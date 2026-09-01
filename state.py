import copy
import re
import threading

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

# Internal trackers. These are deliberately in-memory presentation/correlation state;
# SQLite remains the durable evidence store.
_event_count = 0
_source_activity = {}
_target_counts = {}

_STAGE_ORDER = ["Discovery", "Service Probe", "Access Attempt", "Escalation"]

# Signals are grouped by meaning so classification is not a single brittle keyword list.
# The canonical event model is intentionally small, therefore these text indicators are
# combined with quantitative/contextual signals (attempt_count, history, risk context).
_SENSITIVE_SERVICES = (
    "admin system",
    "administrative system",
    "digital vault",
    "management console",
    "management plane",
    "domain controller",
    "secrets vault",
    "privileged access",
)

_HIGH_IMPACT_EVENTS = (
    "privilege escalation",
    "remote code execution",
    "command execution",
    "reverse shell",
    "shell access",
    "credential dumping",
    "data exfiltration",
    "exfiltration",
    "ransomware",
    "malware execution",
    "lateral movement",
    "persistence",
    "account takeover",
    "successful exploit",
    "exploit success",
    # Preserved from the original state contract: an explicit access-attempt event
    # is considered a critical transition in the workshop model.
    "access attempt",
)

_RECON_SIGNALS = (
    "port scan",
    "nmap",
    "syn scan",
    "network scan",
    "port sweep",
    "service discovery",
    "reconnaissance",
    "enumeration",
    "banner grab",
    "probe",
)

_AUTH_ATTACK_SIGNALS = (
    "brute force",
    "password spray",
    "credential stuffing",
    "authentication failure",
    "login failure",
)

_EXPLOIT_ATTEMPT_SIGNALS = (
    "exploit attempt",
    "sql injection",
    "command injection",
    "path traversal",
    "directory traversal",
    "file inclusion",
)

_AVAILABILITY_ATTACK_SIGNALS = (
    "ddos",
    "dos attack",
    "denial of service",
    "syn flood",
    "connection flood",
)


def _normalize_text(value) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\s_\-/]+", " ", value.strip().lower())


def _matches_any(text: str, indicators) -> bool:
    """Match complete tokens/phrases while avoiding accidental substrings."""
    normalized = _normalize_text(text)
    for indicator in indicators:
        needle = _normalize_text(indicator)
        if not needle:
            continue
        if " " in needle:
            if needle in normalized:
                return True
        elif re.search(rf"\b{re.escape(needle)}\b", normalized):
            return True
    return False


def _event_metrics(event: dict) -> tuple[int, int, int]:
    """Return trusted-shape metrics with conservative defaults."""
    attempts = event.get("attempt_count", 1)
    if type(attempts) is not int or attempts < 1:
        attempts = 1

    related = event.get("previous_related_events", [])
    related_count = len(related) if isinstance(related, list) else 0

    risk_context = event.get("current_risk_context", {})
    context_risk = risk_context.get("risk_score", 0) if isinstance(risk_context, dict) else 0
    if type(context_risk) is not int or not 0 <= context_risk <= 100:
        context_risk = 0

    return attempts, related_count, context_risk


def _is_sensitive_event(event_type: str, service: str, event: dict | None = None) -> bool:
    """
    Determine whether an event justifies an immediate critical transition.

    This intentionally combines asset criticality, high-impact attack semantics and
    behavioural context. Reconnaissance such as Nmap/port scans is hostile and is
    handled as suspicious, but is not automatically promoted to CRITICAL unless the
    event also carries strong impact/volume/context evidence.
    """
    event_type_text = _normalize_text(event_type)
    service_text = _normalize_text(service)
    event = event if isinstance(event, dict) else {}
    attempts, related_count, context_risk = _event_metrics(event)

    # A hit on a protected logical asset is critical even when the event label is
    # generic (preserves the existing Admin System / Digital Vault contract).
    if _matches_any(service_text, _SENSITIVE_SERVICES):
        return True

    # Explicit post-compromise/high-impact actions are inherently critical.
    if _matches_any(event_type_text, _HIGH_IMPACT_EVENTS):
        return True

    # High-volume availability attacks can be critical without relying on an exact
    # product-specific event label beyond the broad attack family.
    if _matches_any(event_type_text, _AVAILABILITY_ATTACK_SIGNALS) and attempts >= 50:
        return True

    # Unknown/vendor-specific event labels can still escalate when multiple
    # independent behavioural signals agree. The upstream risk context is never
    # sufficient by itself; it only corroborates volume + correlation history.
    if attempts >= 50 and related_count >= 1 and context_risk >= 80:
        return True

    return False


def _is_suspicious_event(event: dict) -> bool:
    """Detect hostile/reconnaissance behaviour that warrants observation/risk 48."""
    event_type = event.get("event_type", "")
    attempts, related_count, context_risk = _event_metrics(event)

    if _matches_any(event_type, _RECON_SIGNALS):
        return True
    if _matches_any(event_type, _AUTH_ATTACK_SIGNALS):
        return True
    if _matches_any(event_type, _EXPLOIT_ATTEMPT_SIGNALS):
        return True
    if _matches_any(event_type, _AVAILABILITY_ATTACK_SIGNALS):
        return True

    # Behavioural fallbacks catch vendor-specific labels and high-rate activity.
    if attempts >= 10:
        return True
    if related_count >= 2:
        return True
    if context_risk >= 50 and (attempts >= 3 or related_count >= 1):
        return True

    return False


def _stage_for_suspicious_event(event: dict) -> str:
    event_type = event.get("event_type", "")
    _, related_count, context_risk = _event_metrics(event)

    if _matches_any(event_type, _AUTH_ATTACK_SIGNALS) or _matches_any(event_type, _EXPLOIT_ATTEMPT_SIGNALS):
        return "Access Attempt"
    if context_risk >= 70 and related_count >= 1:
        return "Access Attempt"
    return "Service Probe"


def _advance_timeline(stage: str):
    if stage not in _STAGE_ORDER:
        return
    stage_index = _STAGE_ORDER.index(stage)
    for item in _STAGE_ORDER[: stage_index + 1]:
        if item not in _timeline:
            _timeline.append(item)


def _most_targeted_asset():
    if not _target_counts:
        return None
    # Dict insertion order provides deterministic tie-breaking in favour of the
    # first asset to reach the maximum count.
    return max(_target_counts, key=_target_counts.get)


def process_event(event: dict) -> dict:
    """
    Process a normalized local event and progress the presentation state immediately.

    The global state remains compatible with the workshop UI, while correlation counts
    are maintained per source so interleaved attackers do not erase one another's
    history. Risk never decreases as a side effect of receiving a new source.
    """
    global _current_state, _current_risk, _current_stage, _current_source
    global _event_count, _source_activity, _target_counts

    with _lock:
        source = event.get("source", "Unknown")
        service = event.get("target_service", "")
        event_type = event.get("event_type", "")

        source = source if isinstance(source, str) and source else "Unknown"
        service = service if isinstance(service, str) else ""
        event_type = event_type if isinstance(event_type, str) else ""

        _event_count += 1
        _source_activity[source] = _source_activity.get(source, 0) + 1
        source_count = _source_activity[source]
        if service:
            _target_counts[service] = _target_counts.get(service, 0) + 1

        _current_source = source
        is_sensitive = _is_sensitive_event(event_type, service, event)
        is_suspicious = _is_suspicious_event(event)

        if is_sensitive:
            update_risk(max(_current_risk, 91))
            transition_state(CRITICAL_INTRUSION)
            _current_stage = "Escalation"
            _advance_timeline("Escalation")

        elif _current_state == CRITICAL_INTRUSION:
            # Never create an internally inconsistent state such as
            # CRITICAL_INTRUSION with risk 21 or a regressed Service Probe stage.
            update_risk(max(_current_risk, 91))
            _current_stage = "Escalation"
            _advance_timeline("Escalation")

        elif is_suspicious:
            update_risk(max(_current_risk, 48))
            if _current_state == NORMAL:
                transition_state(UNDER_OBSERVATION)
            if _current_state in (NORMAL, UNDER_OBSERVATION):
                _current_stage = _stage_for_suspicious_event(event)
                _advance_timeline(_current_stage)

        elif source_count == 1:
            update_risk(max(_current_risk, 21))
            if _current_state == NORMAL:
                transition_state(UNDER_OBSERVATION)
            if _current_state in (NORMAL, UNDER_OBSERVATION):
                _current_stage = "Discovery"
                _advance_timeline("Discovery")

        else:
            # Repeated activity from a known source raises observation risk but does
            # not become critical solely because the event count increased.
            update_risk(max(_current_risk, 48))
            if _current_state == NORMAL:
                transition_state(UNDER_OBSERVATION)
            if _current_state in (NORMAL, UNDER_OBSERVATION):
                _current_stage = "Service Probe"
                _advance_timeline("Service Probe")

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

        # Don't downgrade from critical directly back to observation in normal flow.
        if _current_state == CRITICAL_INTRUSION and new_state in (NORMAL, UNDER_OBSERVATION):
            if new_state != NORMAL:
                return

        _current_state = new_state


def reset_state():
    global _current_state, _current_risk, _current_stage, _current_source
    global _timeline, _generation, _ai_result, _event_count
    global _source_activity, _target_counts

    with _lock:
        _generation += 1
        _current_state = NORMAL
        _current_risk = 0
        _current_stage = None
        _current_source = None
        _timeline = []
        _event_count = 0
        _source_activity = {}
        _target_counts = {}
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
            "ai_result": copy.deepcopy(_ai_result) if _ai_result else None,
            "event_count": _event_count,
            "most_targeted_asset": _most_targeted_asset(),
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
            # Do not allow AI to downgrade a locally determined critical state.
            _ai_result = copy.deepcopy(result)
            return True
        if ai_severity == "CRITICAL" and _current_state in (NORMAL, UNDER_OBSERVATION):
            transition_state(CRITICAL_INTRUSION)
            update_risk(max(_current_risk, result.get("risk_score", 91)))

        _ai_result = copy.deepcopy(result)
        return True


def contain_threat():
    global _timeline, _current_stage
    with _lock:
        transition_state(CONTAINED)
        _current_stage = "Containment"
        if "Containment" not in _timeline:
            _timeline.append("Containment")


def enter_forensic_mode():
    with _lock:
        transition_state(FORENSIC)


def enter_executive_mode():
    with _lock:
        transition_state(EXECUTIVE)

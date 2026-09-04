import json
import threading
from datetime import datetime, timezone

MAX_PREVIOUS_EVENTS = 8
MAX_SOURCE_HISTORY = 100

# OpenCanary logtype constants verified against thinkst/opencanary source at
# commit 86f0725 (opencanary/logger.py LoggerBase). 5001-5005 are the port-scan
# / Nmap classes emitted by opencanary/modules/portscan.py.
LOGTYPE_MAP = {
    2000: "FTP Login Attempt",
    2001: "FTP Login Attempt",
    3000: "HTTP Request",
    3001: "HTTP Login Attempt",
    3002: "HTTP Probe",
    3003: "HTTP Request",
    4000: "SSH Connection",
    4001: "SSH Version Banner",
    4002: "SSH Login Attempt",
    5000: "SMB File Open",
    5001: "Port Scan",
    5002: "Nmap OS Scan",
    5003: "Nmap NULL Scan",
    5004: "Nmap XMAS Scan",
    5005: "Nmap FIN Scan",
    6001: "Telnet Login Attempt",
    6002: "Telnet Connection",
    7001: "HTTP Proxy Login Attempt",
    8001: "MySQL Login Attempt",
    14001: "RDP Connection",
}

# Protocol family of a honeypot module, used only when no useful destination
# port is present in the payload.
LOGTYPE_SERVICE_FAMILY = {
    2000: "FTP",
    2001: "FTP",
    3000: "HTTP",
    3001: "HTTP",
    3002: "HTTP",
    3003: "HTTP",
    4000: "SSH",
    4001: "SSH",
    4002: "SSH",
    5000: "SMB",
    6001: "Telnet",
    6002: "Telnet",
    7001: "HTTP",
    8001: "MySQL",
    14001: "RDP",
}

SERVICE_PORT_MAP = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    110: "POP3",
    143: "IMAP",
    443: "HTTPS",
    445: "SMB",
    3306: "MySQL",
    3389: "RDP",
    5432: "PostgreSQL",
    5900: "VNC",
}

_TIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
)

_lock = threading.RLock()
_history = {}


def _coerce_logtype(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError("native 'logtype' must be an integer")


def _coerce_port(value):
    if value is None:
        return -1
    if type(value) is int:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    raise ValueError("native 'dst_port' must be an integer or numeric string")


def _native_source(native):
    source = native.get("src_host")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("missing required native field: src_host")
    return source.strip()


def _to_canonical_timestamp(text):
    for fmt in _TIME_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue
    raise ValueError("unrecognised native timestamp format")


def _native_timestamp(native, now):
    for key in ("utc_time", "local_time", "local_time_adjusted"):
        value = native.get(key)
        if isinstance(value, str) and value.strip():
            try:
                return _to_canonical_timestamp(value.strip())
            except ValueError:
                continue
    reference = now() if now is not None else datetime.now(timezone.utc)
    return reference.strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_target_service(native, logtype, port):
    if port is not None and 1 <= port <= 65535:
        name = SERVICE_PORT_MAP.get(port)
        if name:
            return name
        family = LOGTYPE_SERVICE_FAMILY.get(logtype)
        if family:
            return family
        return "Port {0}".format(port)
    family = LOGTYPE_SERVICE_FAMILY.get(logtype)
    if family:
        return family
    return "Unknown Service"


def parse_native_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("native payload must be a JSON object")
    if "message" in payload:
        message = payload["message"]
        if isinstance(message, dict):
            native = message
        elif isinstance(message, str):
            try:
                native = json.loads(message)
            except (TypeError, ValueError):
                raise ValueError("native 'message' field is not valid JSON")
            if not isinstance(native, dict):
                raise ValueError("native 'message' JSON must decode to an object")
        else:
            raise ValueError("native 'message' field must be a string or object")
    else:
        native = payload
    if "src_host" not in native and "logtype" not in native:
        raise ValueError("native event is missing expected fields: src_host/logtype")
    return native


def _record_correlation(source, event_type, service, timestamp):
    with _lock:
        entry = _history.get(source)
        if entry is None:
            entry = {"count": 0, "events": [], "services": set()}
            _history[source] = entry
        previous = [event["summary"] for event in entry["events"]][-MAX_PREVIOUS_EVENTS:]
        attempt_count = entry["count"] + 1
        entry["count"] += 1
        entry["events"].append(
            {
                "timestamp": timestamp,
                "event_type": event_type,
                "service": service,
                "summary": "{0} {1} at {2}".format(source, event_type, service),
            }
        )
        if service:
            entry["services"].add(service)
        if len(entry["events"]) > MAX_SOURCE_HISTORY:
            entry["events"] = entry["events"][-MAX_SOURCE_HISTORY:]
        return attempt_count, previous, sorted(entry["services"])


def adapt_native_event(payload, now=None):
    native = parse_native_payload(payload)
    source = _native_source(native)
    logtype = _coerce_logtype(native.get("logtype"))
    event_type = LOGTYPE_MAP.get(logtype)
    if event_type is None:
        raise ValueError("unsupported native logtype: {0}".format(logtype))
    port = _coerce_port(native.get("dst_port", -1))
    target_service = _resolve_target_service(native, logtype, port)
    timestamp = _native_timestamp(native, now)
    attempt_count, previous_related_events, _ = _record_correlation(
        source, event_type, target_service, timestamp
    )
    return {
        "event_type": event_type,
        "source": source,
        "target_service": target_service,
        "timestamp": timestamp,
        "attempt_count": attempt_count,
        "previous_related_events": previous_related_events,
    }


def reset_correlation():
    with _lock:
        _history.clear()


def source_correlation(source):
    with _lock:
        entry = _history.get(source)
        if entry is None:
            return {"attempt_count": 0, "services": [], "events": []}
        return {
            "attempt_count": entry["count"],
            "services": sorted(entry["services"]),
            "events": list(entry["events"]),
        }

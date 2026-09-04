import unittest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import opencanary_adapter as adapter


def native_event(**overrides):
    event = {
        "src_host": "203.0.113.10",
        "src_port": "53000",
        "dst_host": "192.0.2.50",
        "dst_port": "22",
        "logtype": 5001,
        "logdata": {},
        "node_id": "canary-1",
        "utc_time": "2026-08-23 10:00:00.000000",
        "local_time": "2026-08-23 10:00:00.000000",
        "local_time_adjusted": "2026-08-23 12:00:00.000000",
    }
    event.update(overrides)
    return event


def wrapped(native):
    return {"message": json.dumps(native)}


class TestOpenCanaryAdapter(unittest.TestCase):
    def setUp(self):
        adapter.reset_correlation()

    def test_valid_native_event_parsing(self):
        canonical = adapter.adapt_native_event(wrapped(native_event()))
        self.assertEqual(canonical["event_type"], "Port Scan")
        self.assertEqual(canonical["source"], "203.0.113.10")
        self.assertEqual(canonical["target_service"], "SSH")
        self.assertEqual(canonical["timestamp"], "2026-08-23T10:00:00Z")
        self.assertGreaterEqual(canonical["attempt_count"], 1)
        self.assertIsInstance(canonical["previous_related_events"], list)

    def test_wrapped_message_json_parsing(self):
        wrapped_canonical = adapter.adapt_native_event(wrapped(native_event()))
        direct_canonical = adapter.adapt_native_event(
            native_event(src_host="198.51.100.5")
        )
        for key in ("event_type", "target_service", "timestamp"):
            self.assertEqual(wrapped_canonical[key], direct_canonical[key])
        self.assertEqual(wrapped_canonical["source"], "203.0.113.10")
        self.assertEqual(direct_canonical["source"], "198.51.100.5")

    def test_malformed_message_rejected(self):
        with self.assertRaises(ValueError):
            adapter.adapt_native_event({"message": "not valid json"})

    def test_missing_source_rejected(self):
        no_source = native_event()
        del no_source["src_host"]
        with self.assertRaises(ValueError):
            adapter.adapt_native_event(wrapped(no_source))
        with self.assertRaises(ValueError):
            adapter.adapt_native_event(wrapped(native_event(src_host="")))

    def test_invalid_source_type_rejected(self):
        with self.assertRaises(ValueError):
            adapter.adapt_native_event(wrapped(native_event(src_host=123)))
        with self.assertRaises(ValueError):
            adapter.adapt_native_event(wrapped(native_event(src_host=["10.0.0.1"])))

    def test_destination_port_mapping(self):
        cases = {
            21: "FTP",
            22: "SSH",
            23: "Telnet",
            80: "HTTP",
            443: "HTTPS",
            445: "SMB",
            3306: "MySQL",
            3389: "RDP",
        }
        for port, expected in cases.items():
            with self.subTest(port=port):
                canonical = adapter.adapt_native_event(
                    wrapped(native_event(dst_port=str(port), src_host="198.51.100.9"))
                )
                self.assertEqual(canonical["target_service"], expected)

    def test_unknown_port_handled_safely(self):
        canonical = adapter.adapt_native_event(
            wrapped(native_event(dst_port="8080", src_host="198.51.100.11"))
        )
        self.assertEqual(canonical["target_service"], "Port 8080")
        canonical_module = adapter.adapt_native_event(
            wrapped(
                native_event(
                    dst_port="2222",
                    logtype=4002,
                    src_host="198.51.100.12",
                )
            )
        )
        self.assertEqual(canonical_module["target_service"], "SSH")

    def test_timestamp_preserved(self):
        canonical = adapter.adapt_native_event(wrapped(native_event()))
        self.assertEqual(canonical["timestamp"], "2026-08-23T10:00:00Z")
        self.assertNotEqual(
            canonical["timestamp"][:10], "2026-09-02"
        )

    def test_source_correlation_increments(self):
        first = adapter.adapt_native_event(wrapped(native_event()))
        second = adapter.adapt_native_event(
            wrapped(native_event(dst_port="80", logtype=3000))
        )
        third = adapter.adapt_native_event(
            wrapped(native_event(dst_port="443", logtype=5002))
        )
        self.assertEqual(first["attempt_count"], 1)
        self.assertEqual(second["attempt_count"], 2)
        self.assertEqual(third["attempt_count"], 3)
        self.assertEqual(len(third["previous_related_events"]), 2)
        self.assertEqual(
            adapter.source_correlation("203.0.113.10")["attempt_count"], 3
        )
        other = adapter.adapt_native_event(
            wrapped(native_event(src_host="10.9.9.9"))
        )
        self.assertEqual(other["attempt_count"], 1)

    def test_reset_clears_correlation(self):
        adapter.adapt_native_event(wrapped(native_event()))
        adapter.adapt_native_event(wrapped(native_event()))
        self.assertEqual(
            adapter.source_correlation("203.0.113.10")["attempt_count"], 2
        )
        adapter.reset_correlation()
        after = adapter.adapt_native_event(wrapped(native_event()))
        self.assertEqual(after["attempt_count"], 1)
        self.assertEqual(after["previous_related_events"], [])

    def test_missing_logtype_rejected(self):
        no_logtype = native_event()
        del no_logtype["logtype"]
        with self.assertRaises(ValueError):
            adapter.adapt_native_event(wrapped(no_logtype))

    def test_unsupported_logtype_rejected(self):
        with self.assertRaises(ValueError):
            adapter.adapt_native_event(wrapped(native_event(logtype=999999)))


class TestNmapLogtypeMapping(unittest.TestCase):
    def setUp(self):
        adapter.reset_correlation()

    def _adapt(self, logtype):
        return adapter.adapt_native_event(
            wrapped(native_event(logtype=logtype, src_host="203.0.113.20"))
        )

    def test_logtype_5001_syn_scan_maps_to_port_scan(self):
        self.assertEqual(self._adapt(5001)["event_type"], "Port Scan")

    def test_logtype_5002_os_scan_maps_to_nmap_os_scan(self):
        self.assertEqual(self._adapt(5002)["event_type"], "Nmap OS Scan")

    def test_logtype_5003_null_scan_maps_to_nmap_null_scan(self):
        self.assertEqual(self._adapt(5003)["event_type"], "Nmap NULL Scan")

    def test_logtype_5004_xmas_scan_maps_to_nmap_xmas_scan(self):
        self.assertEqual(self._adapt(5004)["event_type"], "Nmap XMAS Scan")

    def test_logtype_5005_fin_scan_maps_to_nmap_fin_scan(self):
        self.assertEqual(self._adapt(5005)["event_type"], "Nmap FIN Scan")

    def test_logtype_values_match_opencanary_constants(self):
        self.assertEqual(adapter.LOGTYPE_MAP[5001], "Port Scan")
        self.assertEqual(adapter.LOGTYPE_MAP[5002], "Nmap OS Scan")
        self.assertEqual(adapter.LOGTYPE_MAP[5003], "Nmap NULL Scan")
        self.assertEqual(adapter.LOGTYPE_MAP[5004], "Nmap XMAS Scan")
        self.assertEqual(adapter.LOGTYPE_MAP[5005], "Nmap FIN Scan")


if __name__ == "__main__":
    unittest.main()

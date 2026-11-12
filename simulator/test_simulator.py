"""Deterministic simulator validation without a broker or real GPIO outputs."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from telemetry_simulator import SimulatedDevice, parse_command


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.published = []

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def publish(self, topic, payload, **kwargs):
        self.published.append((topic, json.loads(payload)))


def command(identifier="12345678-abcd-1234-abcd-123456789abc"):
    return {"command_id": identifier, "key": "A", "value": 1,
            "issued_at_ms": 10000, "expires_at_ms": 20000}


class CommandParsingTests(unittest.TestCase):
    def test_valid(self):
        self.assertIsNone(parse_command(json.dumps(command()).encode(), False, 11000)[1])

    def test_retained_and_expiry(self):
        data = json.dumps(command()).encode()
        self.assertEqual(parse_command(data, True, 11000)[1], "retained_command_forbidden")
        self.assertEqual(parse_command(data, False, 20000)[1], "expired")

    def test_future_and_ttl(self):
        data = command()
        self.assertEqual(parse_command(json.dumps(data).encode(), False, 5000)[1], "future_command")
        data["expires_at_ms"] = 50000
        self.assertEqual(parse_command(json.dumps(data).encode(), False, 11000)[1], "ttl_exceeded")

    def test_schema_rejects_bool_fraction_bad_key_uuid_extra_field(self):
        for field, value in (("value", True), ("value", 0.5), ("key", "C"),
                             ("command_id", "not-uuid"), ("extra", 1)):
            with self.subTest(field=field, value=value):
                data = command(); data[field] = value
                with self.assertRaises(ValueError):
                    parse_command(json.dumps(data).encode(), False, 11000)

    def test_duplicate_json_and_oversize(self):
        with self.assertRaises(ValueError):
            parse_command(b'{"key":"A","key":"B"}', False, 11000)
        with self.assertRaises(ValueError):
            parse_command(b"x" * 512, False, 11000)


class DeviceTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"MQTT_DEVICE_PASSWORD": "unit-test", "SIMULATOR_CONTROL_TIMEOUT_SECONDS": "60"})
        self.environment.start()
        self.client = patch("telemetry_simulator.mqtt.Client", FakeClient)
        self.client.start()
        self.device = SimulatedDevice("ESP32_001", "127.0.0.1", 1883)

    def tearDown(self):
        self.client.stop(); self.environment.stop()

    def submit(self, data):
        message = SimpleNamespace(topic=self.device.topic("command"), payload=json.dumps(data).encode(), retain=False)
        with patch("telemetry_simulator.time.time_ns", return_value=11_000_000_000), patch("telemetry_simulator.time.monotonic", return_value=100.0):
            self.device.on_message(self.device.client, None, message)

    def statuses(self):
        return [payload["status"] for topic, payload in self.device.client.published if topic.endswith("/ack")]

    def test_apply_dedupe_disconnect(self):
        data = command(); self.submit(data)
        self.assertEqual(self.device.controls["A"], 1)
        self.assertEqual(self.statuses(), ["accepted", "applied"])
        self.device.on_disconnect(None, None, None, None, None)
        self.submit(data)
        self.assertEqual(self.device.controls["A"], 0)
        self.assertEqual(self.statuses(), ["accepted", "applied", "rejected"])

    def test_watchdog(self):
        self.submit(command()); self.device.expire_controls(161.0)
        self.assertEqual(self.device.controls, {"A": 0, "B": 0})

    def test_full_cache_preserves_replay_guards(self):
        for index in range(65):
            self.submit(command(f"12345678-abcd-1234-abcd-{index:012x}"))
        self.assertEqual(len(self.device.commands), 64)
        self.assertEqual(self.statuses().count("applied"), 64)
        self.assertEqual(self.statuses()[-1], "rejected")

    def test_bad_device_identifier(self):
        with self.assertRaises(ValueError):
            SimulatedDevice("+/all", "127.0.0.1", 1883)

    def test_custom_prefix_and_invalid_prefix(self):
        with patch.dict(os.environ, {"MQTT_TOPIC_PREFIX": "local_nav"}):
            device = SimulatedDevice("ESP32_001", "127.0.0.1", 1883)
            self.assertEqual(device.topic("telemetry"), "local_nav/ESP32_001/telemetry")
        with patch.dict(os.environ, {"MQTT_TOPIC_PREFIX": "#/all"}):
            with self.assertRaises(ValueError):
                SimulatedDevice("ESP32_001", "127.0.0.1", 1883)


if __name__ == "__main__":
    unittest.main()

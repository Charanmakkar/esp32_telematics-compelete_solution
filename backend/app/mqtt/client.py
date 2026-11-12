import json
import logging

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MqttClient:
    def __init__(self, settings, receive):
        self.settings = settings
        self.connected = False
        self.receive = receive
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id="navsphere-backend", clean_session=True
        )
        self.client.max_queued_messages_set(128)
        self.client.max_inflight_messages_set(20)
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        if settings.mqtt_tls:
            self.client.tls_set(ca_certs=settings.mqtt_ca_file)
        self.client.on_connect = self._connect
        self.client.on_disconnect = self._disconnect
        self.client.on_message = self._message

    def _connect(self, client, userdata, flags, reason_code, properties):
        self.connected = not reason_code.is_failure
        if self.connected:
            topics = [
                (f"{self.settings.mqtt_topic_prefix}/{d}/{kind}", 1)
                for d in self.settings.allowed_devices
                for kind in ("telemetry", "ack", "status")
            ]
            result, _ = client.subscribe(topics)
            if result != mqtt.MQTT_ERR_SUCCESS:
                logger.error("mqtt_subscription_failed")
        logger.info("mqtt_connected=%s", self.connected)

    def _disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected = False
        logger.warning("mqtt_disconnected")

    def _message(self, client, userdata, message):
        # No JSON decoding, database work, or event-loop scheduling in this callback.
        self.receive(message.topic, message.payload, message.retain)

    def start(self):
        if self.settings.mqtt_enabled:
            self.client.connect_async(self.settings.mqtt_host, self.settings.mqtt_port, 60)
            self.client.loop_start()

    def stop(self):
        if self.settings.mqtt_enabled:
            self.client.disconnect()
            self.client.loop_stop()

    def publish_command(self, device_id: str, payload: dict) -> bool:
        if not self.connected:
            return False
        info = self.client.publish(
            f"{self.settings.mqtt_topic_prefix}/{device_id}/command",
            json.dumps(payload, separators=(",", ":")),
            qos=1,
            retain=False,
        )
        return info.rc == mqtt.MQTT_ERR_SUCCESS

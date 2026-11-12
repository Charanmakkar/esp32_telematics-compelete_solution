"""Run the telemetry simulator's logical A/B responder without physical outputs.

The telemetry simulator includes the command responder so one MQTT client owns the
device identity. This entry point shares that implementation intentionally.
"""
from telemetry_simulator import main

if __name__ == "__main__":
    main()

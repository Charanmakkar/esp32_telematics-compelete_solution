"""Bench CAN acknowledgement receiver. Never sends application CAN messages.

Keep PCAN connected while the BMS and listen-only ESP32 are the only other
nodes. Stop this process when another normal-mode node supplies acknowledgements.
"""
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import can

root=Path(__file__).resolve().parents[1]
counts=Counter()
errors=0
last=0
with can.Bus(interface='pcan',channel='PCAN_USBBUS1',bitrate=500000,state=can.BusState.ACTIVE) as bus:
    while True:
        message=bus.recv(.1)
        if message:
            if message.is_error_frame:errors+=1
            else:counts[f'0x{message.arbitration_id:X}']+=1
        now=time.monotonic()
        if now-last>=5:
            report={'time_utc':datetime.now(timezone.utc).isoformat(),'mode':'normal receiver (ACK enabled)',
                    'application_messages_sent':0,'frames':sum(counts.values()),'ids':dict(counts),
                    'error_frames':errors,'pcan_status':bus.status_string()}
            (root/'.runtime/pcan-receiver-status.json').write_text(json.dumps(report,indent=2))
            last=now

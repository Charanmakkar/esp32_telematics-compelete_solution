from pathlib import Path
import serial,time
root=Path(__file__).resolve().parents[1]
port=serial.Serial();port.port='COM3';port.baudrate=115200;port.timeout=.1;port.dtr=False;port.rts=False;port.open()
stop=root/'.runtime/ota-serial-stop'
print('Serial capture started',flush=True)
try:
    with (root/'.runtime/ota-full-transfer-serial.log').open('wb') as log:
        deadline=time.monotonic()+900
        while time.monotonic()<deadline and not stop.exists():
            log.write(port.read(4096));log.flush()
finally:port.close()
print('Serial capture stopped',flush=True)

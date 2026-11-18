"""Bounded, per-device traffic statistics; no extra raw-history database scans."""

from collections import Counter, deque
from statistics import mean, pstdev
from threading import RLock
from time import monotonic


class CanStatistics:
    def __init__(self):
        self.lock = RLock()
        self.devices = {}

    def observe(self, batch):
        now = monotonic()
        with self.lock:
            state = self.devices.get(batch.device_id)
            if state is None or state["boot_id"] != batch.boot_id:
                state = dict(
                    boot_id=batch.boot_id,
                    started=now,
                    updated=now,
                    buckets=deque(maxlen=61),
                    ids={},
                    counts=Counter(),
                    hardware=deque(maxlen=121),
                    stats={},
                    last_sequence=-1,
                )
                self.devices[batch.device_id] = state
            state["updated"] = now
            state["stats"] = batch.stats.model_dump()
            if not state["buckets"] or state["buckets"][-1]["second"] != int(now):
                state["buckets"].append(dict(second=int(now), counts=Counter()))
            counts = state["buckets"][-1]["counts"]
            for frame in batch.frames:
                if frame.sequence <= state["last_sequence"]:
                    continue
                state["last_sequence"] = frame.sequence
                data_bytes = 0 if frame.rtr else frame.dlc
                for key, value in [
                    ("frames", 1),
                    ("bytes", data_bytes),
                    ("extended" if frame.extended else "standard", 1),
                    ("rtr" if frame.rtr else "data", 1),
                    (f"dlc_{frame.dlc}", 1),
                ]:
                    counts[key] += value
                    state["counts"][key] += value
                key = (frame.can_id, frame.extended, frame.rtr)
                if key not in state["ids"]:
                    if len(state["ids"]) >= 4096:
                        oldest = min(state["ids"], key=lambda k: state["ids"][k]["seen"])
                        del state["ids"][oldest]
                    state["ids"][key] = dict(
                        count=0,
                        intervals=deque(maxlen=64),
                        uptime=None,
                        seen=now,
                        changes=0,
                        data=None,
                        dlc=frame.dlc,
                    )
                record = state["ids"][key]
                if record["uptime"] is not None and frame.uptime_ms >= record["uptime"]:
                    record["intervals"].append(frame.uptime_ms - record["uptime"])
                if record["data"] is not None and record["data"] != frame.data:
                    record["changes"] += 1
                record.update(
                    count=record["count"] + 1,
                    uptime=frame.uptime_ms,
                    seen=now,
                    data=frame.data,
                    dlc=frame.dlc,
                )
            stats = state["stats"]
            if stats.get("uptime_ms") is not None:
                if not state["hardware"] or now - state["hardware"][-1][0] >= 0.5:
                    state["hardware"].append((now, stats))

    def snapshot(self, device_id):
        now = monotonic()
        with self.lock:
            state = self.devices.get(device_id)
            if state is None:
                return {"available": False, "reason": "Waiting for CAN traffic/status"}
            window = Counter()
            for bucket in state["buckets"]:
                if bucket["second"] >= int(now) - 9:
                    window.update(bucket["counts"])
            seconds = max(1, min(10, now - state["started"]))
            hardware = state["hardware"]
            rate = payload_rate = low = high = None
            if len(hardware) >= 2 and now - state["updated"] < 5:
                end = hardware[-1][1]
                start = next((s for t, s in hardware if t >= now - 10), hardware[0][1])
                duration = (end["uptime_ms"] - start["uptime_ms"]) / 1000
                if duration > 0:

                    def delta(key):
                        a, b = start.get(key), end.get(key)
                        return (
                            (b - a) / duration
                            if a is not None and b is not None and b >= a
                            else None
                        )

                    rate, payload_rate = delta("rx_total"), delta("rx_bytes")
                    bits_low, bits_high = delta("wire_bits_min"), delta("wire_bits_max")
                    if bits_low is not None and bits_high is not None:
                        low, high = round(bits_low / 5000, 2), min(100, round(bits_high / 5000, 2))
            items = []
            for (can_id, extended, rtr), record in state["ids"].items():
                intervals = list(record["intervals"])
                average = mean(intervals) if intervals else None
                items.append(
                    dict(
                        can_id=can_id,
                        extended=extended,
                        rtr=rtr,
                        frames=record["count"],
                        dlc=record["dlc"],
                        age_seconds=round(now - record["seen"], 2),
                        changes=record["changes"],
                        mean_interval_ms=round(average, 2) if average is not None else None,
                        min_interval_ms=min(intervals) if intervals else None,
                        max_interval_ms=max(intervals) if intervals else None,
                        jitter_ms=round(pstdev(intervals), 2) if intervals else None,
                        frequency_hz=round(1000 / average, 2) if average else None,
                    )
                )
            items.sort(key=lambda row: (-row["frames"], row["can_id"]))
            return dict(
                available=True,
                boot_id=state["boot_id"],
                age_seconds=round(now - state["updated"], 2),
                uptime_seconds=round(now - state["started"], 1),
                window_seconds=round(seconds, 1),
                received_fps=round(window["frames"] / seconds, 2),
                received_bytes_per_second=round(window["bytes"] / seconds, 2),
                hardware_fps=round(rate, 2) if rate is not None else None,
                hardware_bytes_per_second=round(payload_rate, 2)
                if payload_rate is not None
                else None,
                load_min_percent=low,
                load_max_percent=high,
                unique_ids=len(items),
                totals=dict(state["counts"]),
                dlc_distribution=[state["counts"][f"dlc_{i}"] for i in range(9)],
                device=state["stats"],
                ids=items[:100],
                timing_note=(
                    "Per-ID timing uses the last 64 delivered intervals; capture drops"
                    " affect these values."
                ),
                load_note=(
                    "Estimated wire-time bounds for hardware-captured valid frames, "
                    "including possible bit stuffing and intermission. Missed frames "
                    "and error frames are excluded."
                ),
            )

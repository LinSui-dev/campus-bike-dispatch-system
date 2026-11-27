"""poisson-exp-v1: isolated RNG, stable OD/interval order, integer-second events."""
from math import floor, log1p
from random import Random


def generate_requests(scenario, params, seed):
    rng = Random(seed)
    duration, step = params["duration_min"] * 60, params["step_sec"]
    events = []
    for od in sorted(scenario["od_demands"], key=lambda o: (o["origin_id"], o["destination_id"])):
        boundaries = set(range(0, duration + 1, step)) | {duration}
        for period in od["periods"]:
            boundaries.update((period["start_min"] * 60, period["end_min"] * 60))
        boundaries = sorted(boundaries)
        for start, end in zip(boundaries, boundaries[1:]):
            multiplier = next((p["multiplier"] for p in od["periods"]
                               if p["start_min"] * 60 <= start < p["end_min"] * 60), 1)
            rate = od["rate_per_min"] * multiplier / 60
            if rate == 0:
                continue
            t = start
            while True:
                t += -log1p(-rng.random()) / rate
                if t >= end:
                    break
                time_sec = floor(t)
                events.append({"id": f"req-{len(events) + 1:012d}", "time_sec": time_sec,
                               "executed_sec": time_sec // step * step,
                               "origin_id": od["origin_id"], "destination_id": od["destination_id"]})
    return sorted(events, key=lambda e: (e["time_sec"], e["id"]))

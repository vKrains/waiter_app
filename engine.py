from collections import defaultdict

MAIN_POSITIONS = list(range(1, 19))

WEEKEND_ZONES = {
    "Small": 4,
    "Far": 3,
    "Veranda": 9,
}


def build_history_stats(history):
    total_shifts = defaultdict(int)
    last_main_position = {}

    for h in history:
        wid = int(h["waiter_id"])
        total_shifts[wid] += 1
        if h["zone"] == "Main":
            last_main_position[wid] = h["position"]

    return total_shifts, last_main_position


def next_main_position(wid, free_main, last_main_position):
    last_pos = last_main_position.get(wid)

    if last_pos is None:
        return min(free_main)

    for step in range(1, 19):
        p = ((last_pos - 1 + step) % 18) + 1
        if p in free_main:
            return p

    return min(free_main)


def assign_shift(present, requests, history, shift_type):

    present = [int(x) for x in present]
    present_set = set(present)

    assignments = {}
    locked = set()

    free_main = set(MAIN_POSITIONS)
    free_zones = WEEKEND_ZONES.copy()

    total_shifts, last_main_position = build_history_stats(history)

    for wid, req in requests.items():

        if wid not in present_set:
            continue

        zone = req["zone"]
        pos = req["position"]

        if zone == "Main":

            if pos not in free_main:
                raise ValueError(f"Позиция {pos} уже занята")

            assignments[wid] = {"zone": "Main", "position": pos}
            free_main.remove(pos)

        else:

            if free_zones.get(zone, 0) <= 0:
                continue

            assignments[wid] = {"zone": zone, "position": None}
            free_zones[zone] -= 1

        locked.add(wid)

    remaining = [w for w in present if w not in locked]

    import random
    random.shuffle(remaining)


    # MAIN
    need_main = 18 - sum(1 for a in assignments.values() if a["zone"] == "Main")

    for wid in remaining[:]:
        if need_main <= 0:
            break
        if not free_main:
            break

        pos = next_main_position(wid, free_main, last_main_position)

        assignments[wid] = {"zone": "Main", "position": pos}
        free_main.remove(pos)
        remaining.remove(wid)
        need_main -= 1

    # WEEKEND
    if shift_type == "weekend":

        for zone, max_count in WEEKEND_ZONES.items():

            if not remaining:
                break

            real_count = min(max_count, len(remaining))

            for _ in range(real_count):
                wid = remaining.pop(0)
                assignments[wid] = {"zone": zone, "position": None}

    return assignments

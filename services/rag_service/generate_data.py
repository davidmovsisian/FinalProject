import random
from copy import deepcopy
import json
import re
from pathlib import Path

ROOM_TYPES = [
    "living_room",
    "bed_room",
    "kitchen",
    "bathroom",
    "dinning",
]

OVERALL_CONDITIONS = ["excellent", "good", "fair", "poor"]


def load_seed_data() -> list[dict]:
    data_path = Path(__file__).resolve().parent / "data.json"
    raw_text = data_path.read_text(encoding="utf-8")
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        sanitized = re.sub(r",\s*([\]}])", r"\1", raw_text)
        return json.loads(sanitized)


def derive_room_counts(item: dict) -> dict:
    """Derive the new flat room-count fields from the seed item.

    The old schema stores a flat ``rooms_number`` plus a ``conditions`` list
    whose ``type`` values tell us exactly how many of each room type exist.
    We count those to populate the new explicit fields.
    """
    conditions = item.get("conditions", [])
    type_counts: dict[str, int] = {}
    for c in conditions:
        t = c.get("type", "")
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "living_room": type_counts.get("living_room", 1),
        "bed_rooms": type_counts.get("bed_room", 0),
        "kitchen": type_counts.get("kitchen", 1),
        "bath_rooms": type_counts.get("bathroom", 1),
    }


def derive_overall_condition(conditions: list[dict]) -> str:
    """Map the average condition score across all rooms to a descriptive label."""
    if not conditions:
        return random.choice(OVERALL_CONDITIONS)
    avg = sum(c.get("condition_score", 3) for c in conditions) / len(conditions)
    if avg >= 4.5:
        return "excellent"
    elif avg >= 3.5:
        return "good"
    elif avg >= 2.5:
        return "fair"
    else:
        return "poor"


def create_conditions(living_room: int, bed_rooms: int, kitchen: int, bath_rooms: int, has_dining: bool) -> list[dict]:
    """Generate randomised RoomCondition entries for the given room counts."""
    conditions = []

    for _ in range(living_room):
        conditions.append({
            "type": "living_room",
            "condition_score": random.randint(1, 5),
            "confidence": round(random.uniform(0.7, 1.0), 2),
        })

    for _ in range(bed_rooms):
        conditions.append({
            "type": "bed_room",
            "condition_score": random.randint(1, 5),
            "confidence": round(random.uniform(0.7, 1.0), 2),
        })

    for _ in range(kitchen):
        conditions.append({
            "type": "kitchen",
            "condition_score": random.randint(1, 5),
            "confidence": round(random.uniform(0.7, 1.0), 2),
        })

    for _ in range(bath_rooms):
        conditions.append({
            "type": "bathroom",
            "condition_score": random.randint(1, 5),
            "confidence": round(random.uniform(0.7, 1.0), 2),
        })

    if has_dining:
        conditions.append({
            "type": "dinning",
            "condition_score": random.randint(1, 5),
            "confidence": round(random.uniform(0.7, 1.0), 2),
        })

    return conditions


data = load_seed_data()

# Pre-compute per-seed-item room counts and dining flag (derived once from the
# original conditions list so every expanded copy stays consistent).
seed_room_info: list[dict] = []
for item in data:
    counts = derive_room_counts(item)
    has_dining = any(c.get("type") == "dinning" for c in item.get("conditions", []))
    seed_room_info.append({**counts, "has_dining": has_dining})

expanded = []
for i in range(250):
    item = deepcopy(data[i % len(data)])
    info = seed_room_info[i % len(data)]

    # Drop the old field that no longer exists in PropertyListing.
    item.pop("rooms_number", None)

    # Populate the new explicit room-count fields.
    item["living_room"] = info["living_room"]
    item["bed_rooms"] = info["bed_rooms"]
    item["kitchen"] = info["kitchen"]
    item["bath_rooms"] = info["bath_rooms"]

    # Generate fresh randomised conditions that match the room counts.
    new_conditions = create_conditions(
        living_room=info["living_room"],
        bed_rooms=info["bed_rooms"],
        kitchen=info["kitchen"],
        bath_rooms=info["bath_rooms"],
        has_dining=info["has_dining"],
    )
    item["conditions"] = new_conditions

    # Derive overall_condition from the freshly generated scores.
    item["overall_condition"] = derive_overall_condition(new_conditions)

    # storage is a yes/no field — randomise it.
    item["storage"] = random.choice(["yes", "no"])

    expanded.append(item)

output_path = Path(__file__).resolve().parent / "expanded_data.json"
with output_path.open("w", encoding="utf-8") as f:
    json.dump(expanded, f, indent=2)

print(f"Written {len(expanded)} listings to {output_path}")
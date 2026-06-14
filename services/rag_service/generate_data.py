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


def load_seed_data() -> list[dict]:
    data_path = Path(__file__).resolve().parent / "data.json"
    raw_text = data_path.read_text(encoding="utf-8")
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        sanitized = re.sub(r",\s*([\]}])", r"\1", raw_text)
        return json.loads(sanitized)


def create_conditions(rooms_number):
    conditions = []

    # Always add living room
    conditions.append({
        "type": "living_room",
        "condition_score": random.randint(1, 5),
        "confidence": round(random.uniform(0.7, 1.0), 2)
    })

    if rooms_number >= 4:
        bedrooms = max(rooms_number - 2, 0)
    else:
        bedrooms = max(rooms_number - 1, 0)

    for _ in range(bedrooms):
        conditions.append({
            "type": "bed_room",
            "condition_score": random.randint(1, 5),
            "confidence": round(random.uniform(0.7, 1.0), 2)
        })

    # Always add kitchen
    conditions.append({
        "type": "kitchen",
        "condition_score": random.randint(1, 5),
        "confidence": round(random.uniform(0.7, 1.0), 2)
    })

    # Always add bathroom
    conditions.append({
        "type": "bathroom",
        "condition_score": random.randint(1, 5),
        "confidence": round(random.uniform(0.7, 1.0), 2)
    })

    if rooms_number >= 4:
        conditions.append({
            "type": "dinning",
            "condition_score": random.randint(1, 5),
            "confidence": round(random.uniform(0.7, 1.0), 2)
        })

    return conditions

data = load_seed_data()
expanded = []
for i in range(250):
    item = deepcopy(data[i % len(data)])
    item["conditions"] = create_conditions(item["rooms_number"])
    expanded.append(item)

output_path = Path(__file__).resolve().parent / "expanded_data.json"
with output_path.open("w", encoding="utf-8") as f:
    json.dump(expanded, f, indent=2)
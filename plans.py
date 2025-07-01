from dataclasses import dataclass
from typing import List
import json
from pathlib import Path

@dataclass(frozen=True)
class Plan:
    id: int
    name: str
    price: float
    duration_days: int
    description: str

def load_plans() -> List[Plan]:
    plans_path = Path(__file__).parent / "texts" / "plans.json"
    with open(plans_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return [Plan(**plan) for plan in data["plans"]]

PLANS: List[Plan] = load_plans()

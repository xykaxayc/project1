import json
import os
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class PaymentMethodData:
    id: str
    name: str
    details: str

def load_payment_methods() -> List[PaymentMethodData]:
    """Загрузка способов оплаты из JSON-файла"""
    path = os.path.join(os.path.dirname(__file__), 'texts', 'payment_methods.json')
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return [PaymentMethodData(**item) for item in data]

PAYMENT_METHODS: List[PaymentMethodData] = load_payment_methods()

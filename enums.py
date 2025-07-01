from enum import Enum, auto

class UserStatus(Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"
    PENDING = "pending"

class PaymentMethod(Enum):
    QIWI = "qiwi"
    CARD = "card"
    SBP = "sbp"
    CRYPTO = "crypto"

class UserRole(Enum):
    USER = "user"
    ADMIN = "admin"

# Пример использования:
# if user.status == UserStatus.ACTIVE.value:
# if payment_method == PaymentMethod.QIWI.value:

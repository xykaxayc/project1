import os
from typing import List
from texts import get_json

# Вынесите бизнес-данные (тарифы, методы оплаты, сообщения) в отдельные файлы:
# plans.py, payment_methods.py, messages.py
# Здесь только переменные окружения и базовые настройки

def _parse_admin_ids() -> List[int]:
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    if not admin_ids_str:
        return []
    admin_ids = []
    for id_str in admin_ids_str.split(","):
        id_str = id_str.strip()
        if id_str.isdigit():
            admin_ids.append(int(id_str))
    return admin_ids

class Config:
    """Класс конфигурации приложения"""
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    MARZBAN_URL = os.getenv("MARZBAN_URL")
    MARZBAN_USERNAME = os.getenv("MARZBAN_USERNAME")
    MARZBAN_PASSWORD = os.getenv("MARZBAN_PASSWORD")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "users_database.db")
    ADMIN_IDS = _parse_admin_ids()

    # Настройки логирования
    LOGGING = {
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "file": "bot.log",
        "level": "INFO",
        "max_bytes": 2 * 1024 * 1024,  # 2 MB
        "backup_count": 5
    }

    # Настройки для новых пользователей (регистрация)
    NEW_USER_SETTINGS = {
        "username_min_length": 4,
        "username_max_length": 32,
        "username_pattern": r"^[A-Za-z0-9_]+$",
        "auto_create": True,
        "trial_days": 3,
        "default_protocols": ["vless"],
        "data_limit_gb": None,  # None = безлимит
    }

    @classmethod
    def validate(cls) -> bool:
        messages = get_json("validators.validation_messages")["config"]
        errors = []
        required_params = [
            ("TELEGRAM_TOKEN", cls.TELEGRAM_TOKEN),
            ("MARZBAN_URL", cls.MARZBAN_URL),
            ("MARZBAN_USERNAME", cls.MARZBAN_USERNAME),
            ("MARZBAN_PASSWORD", cls.MARZBAN_PASSWORD)
        ]
        for param_name, param_value in required_params:
            if not param_value:
                errors.append(messages["param_not_set"].format(param_name=param_name))
        if not cls.ADMIN_IDS:
            errors.append(messages["no_admins"])
        if errors:
            raise ValueError(f"{messages['errors_prefix']}{', '.join(errors)}")
        return True

    @classmethod
    def is_admin(cls, telegram_id: int) -> bool:
        return int(telegram_id) in cls.ADMIN_IDS

# Получение конфигурации (можно расширить для разных окружений через ENVIRONMENT)
def get_config():
    """Получение конфигурации приложения"""
    return Config
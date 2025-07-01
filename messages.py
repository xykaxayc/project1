"""
Модуль совместимости для работы с текстовыми сообщениями.
Предоставляет обратную совместимость со старым форматом сообщений.
Рекомендуется использовать напрямую TextManager из texts/__init__.py.
"""

from texts import get_text, get_json
from typing import Dict, Any

def get_message(key: str, **kwargs) -> str:
    """
    Получение сообщения по ключу с форматированием.
    
    Args:
        key: Ключ сообщения
        **kwargs: Параметры для форматирования
        
    Returns:
        str: Отформатированное сообщение
    """
    return get_text(key, **kwargs)

def get_json_data(key: str) -> Dict[str, Any]:
    """
    Получение данных из JSON файла.
    
    Args:
        key: Ключ файла
        
    Returns:
        Dict[str, Any]: Данные из JSON файла
    """
    return get_json(key)

# Экспорт основных констант для обратной совместимости
MESSAGES = {
    # Общие сообщения
    "welcome": get_text("messages.welcome"),
    "error": get_text("messages.errors.default"),
    "generic_error": get_text("messages.errors.GENERIC_ERROR"),
    
    # Планы и оплата
    "plan_list": get_text("messages.plan_list"),
    "payment_methods": get_text("messages.payment_methods"),
    
    # Регистрация и аккаунты
    "registration_form": get_text("user.registration.REGISTRATION_FORM"),
    "account_created": get_text("user.registration.ACCOUNT_CREATED"),
    "account_linked": get_text("messages.ACCOUNT_LINKED"),
    "welcome_unlinked": get_text("handlers.user_messages.menu.welcome_unlinked"),
    
    # Поддержка и помощь
    "support_info": get_text("user.support.SUPPORT_INFO"),
    "admin_help": get_text("admin.commands"),
}

# Сообщения об ошибках
ERROR_MESSAGES = {
    "no_admin_rights": get_text("messages.errors.NO_ADMIN_RIGHTS"),
    "admin_notification": get_text("messages.errors.ADMIN_NOTIFICATION_ERROR"),
    "unverified_user": get_text("messages.errors.UNVERIFIED_USER"),
    "no_vpn_config": get_text("messages.errors.NO_VPN_CONFIG"),
    "invalid_username": get_text("messages.errors.INVALID_USERNAME"),
    "username_taken": get_text("messages.errors.USERNAME_TAKEN"),
    "account_creation": get_text("messages.errors.ACCOUNT_CREATION_ERROR"),
}

# Добавляем ошибки в основной словарь для обратной совместимости
MESSAGES.update({"errors": ERROR_MESSAGES})

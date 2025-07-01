# DEPRECATED: Используйте text_constants.py для всех текстовых констант и шаблонов!
from texts import get_text, get_json

# Импортируем все необходимые константы из нового менеджера
NO_ADMIN_RIGHTS_TEXT = get_text("messages.errors.NO_ADMIN_RIGHTS")
ADMIN_NOTIFICATION_ERROR_TEXT = get_text("messages.errors.ADMIN_NOTIFICATION_ERROR")
UNVERIFIED_USER_TEXT = get_text("messages.errors.UNVERIFIED_USER")
NO_VPN_CONFIG_ERROR = get_text("messages.errors.NO_VPN_CONFIG")
INVALID_USERNAME_TEXT = get_text("messages.errors.INVALID_USERNAME")
USERNAME_TAKEN_TEXT = get_text("messages.errors.USERNAME_TAKEN")
ACCOUNT_CREATING_TEXT = get_text("user.registration.ACCOUNT_CREATING")
ACCOUNT_CREATION_ERROR_TEXT = get_text("messages.errors.ACCOUNT_CREATION_ERROR")
CONNECTION_MESSAGE_TEMPLATE = get_text("user.subscription.CONNECTION_MESSAGE")

# Загружаем форматы подписок из JSON
SUBSCRIPTION_FORMATS = get_json("templates.subscription_formats")["formats"]

# Константы для источников данных
API_PROVIDED_DESCRIPTION = "Ссылка получена из Marzban API"
API_PROVIDED_SOURCE = "API"

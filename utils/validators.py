import re
import logging
from typing import Optional, Union
from datetime import datetime

from config import get_config
from plans import PLANS
from texts import TextManager, get_json

config = get_config()
logger = logging.getLogger(__name__)

# Преобразуем PLANS в dict для быстрого доступа по id
PLANS_DICT = {str(plan.id): plan for plan in PLANS}

def validate_username(username: str) -> tuple[bool, str]:
    """
    Валидация имени пользователя
    
    Args:
        username: Имя пользователя для проверки
        
    Returns:
        tuple: (is_valid, error_message)
    """
    messages = get_json("validators/validation_messages.json")["username"]
    
    if not username:
        return False, messages["empty"]
    
    username = username.strip()
    settings = config.NEW_USER_SETTINGS
    
    # Проверка длины
    min_len = settings.get('username_min_length', 3)
    max_len = settings.get('username_max_length', 20)
    
    if len(username) < min_len:
        return False, messages["too_short"].format(min_len=min_len)
    
    if len(username) > max_len:
        return False, messages["too_long"].format(max_len=max_len)
    
    # Проверка паттерна
    pattern = settings.get('username_pattern', r"^[a-zA-Z0-9_]+$")
    if not re.match(pattern, username):
        return False, messages["invalid_pattern"]
    
    # Проверка на запрещенные слова
    forbidden_words = ['admin', 'administrator', 'root', 'test', 'demo', 'api', 'bot', 'system']
    if username.lower() in forbidden_words:
        return False, messages["reserved"].format(username=username)
    
    # Проверка на начало и конец с символами
    if username.startswith('_') or username.endswith('_'):
        return False, messages["underscore_boundaries"]
    
    # Проверка на повторяющиеся символы
    if '__' in username:
        return False, messages["double_underscore"]
    
    return True, ""

def validate_payment_amount(amount: Union[str, int, float]) -> tuple[bool, str]:
    """
    Валидация суммы платежа
    
    Args:
        amount: Сумма для проверки
        
    Returns:
        tuple: (is_valid, error_message)
    """
    messages = get_json("validators/validation_messages.json")["payment"]
    
    try:
        amount_float = float(amount)
    except (ValueError, TypeError):
        return False, messages["invalid_amount"]
    
    limits = config.LIMITS
    min_amount = limits.get('min_payment_amount', 100)
    max_amount = limits.get('max_payment_amount', 10000)
    
    if amount_float < min_amount:
        return False, messages["min_amount"].format(min_amount=min_amount)
    
    if amount_float > max_amount:
        return False, messages["max_amount"].format(max_amount=max_amount)
    
    # Проверка на разумные значения (не более 2 знаков после запятой)
    if round(amount_float, 2) != amount_float:
        return False, messages["decimal_places"]
    
    return True, ""

def validate_telegram_id(telegram_id: Union[str, int]) -> tuple[bool, str]:
    """
    Валидация Telegram ID
    
    Args:
        telegram_id: ID для проверки
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        tid = int(telegram_id)
    except (ValueError, TypeError):
        return False, "Telegram ID должен быть числом"
    
    # Telegram ID должен быть положительным числом от 1 до примерно 2^32
    if tid <= 0:
        return False, "Telegram ID должен быть положительным числом"
    
    if tid > 2**32:
        return False, "Неверный формат Telegram ID"
    
    # Проверка на типичные диапазоны Telegram ID
    if tid < 1000:  # Слишком маленький ID
        return False, "Telegram ID слишком мал (возможно, это не настоящий ID)"
    
    return True, ""

def validate_phone_number(phone: str) -> tuple[bool, str]:
    """
    Валидация номера телефона
    
    Args:
        phone: Номер телефона для проверки
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not phone:
        return False, "Номер телефона не может быть пустым"
    
    # Очищаем номер от лишних символов
    cleaned_phone = re.sub(r'[^\d+]', '', phone.strip())
    
    # Проверка базового формата
    if not re.match(r'^\+?[1-9]\d{6,14}$', cleaned_phone):
        return False, "Неверный формат номера телефона"
    
    # Проверка российских номеров
    if cleaned_phone.startswith('+7') or cleaned_phone.startswith('7'):
        if not re.match(r'^(\+7|7)[0-9]{10}$', cleaned_phone):
            return False, "Неверный формат российского номера телефона"
    
    return True, ""

def validate_email(email: str) -> tuple[bool, str]:
    """
    Валидация email адреса
    
    Args:
        email: Email для проверки
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not email:
        return False, "Email не может быть пустым"
    
    email = email.strip().lower()
    
    # Базовая проверка формата email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Неверный формат email адреса"
    
    # Проверка длины
    if len(email) > 254:
        return False, "Email адрес слишком длинный"
    
    # Проверка частей
    local, domain = email.split('@')
    
    if len(local) > 64:
        return False, "Локальная часть email адреса слишком длинная"
    
    if len(domain) > 253:
        return False, "Доменная часть email адреса слишком длинная"
    
    return True, ""

def validate_url(url: str) -> tuple[bool, str]:
    """
    Валидация URL
    
    Args:
        url: URL для проверки
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not url:
        return False, "URL не может быть пустым"
    
    url = url.strip()
    
    # Базовая проверка формата URL
    pattern = r'^https?:\/\/(?:[-\w.])+(?:\:[0-9]+)?(?:\/(?:[\w\._~!$&\'()*+,;=:@]|%[0-9a-fA-F]{2})*)*(?:\?(?:[\w\._~!$&\'()*+,;=:@/?]|%[0-9a-fA-F]{2})*)?(?:#(?:[\w\._~!$&\'()*+,;=:@/?]|%[0-9a-fA-F]{2})*)?$'
    
    if not re.match(pattern, url):
        return False, "Неверный формат URL"
    
    # Проверка длины
    if len(url) > 2000:
        return False, "URL слишком длинный"
    
    return True, ""

def validate_plan_id(plan_id: str) -> tuple[bool, str]:
    """
    Валидация ID плана подписки
    
    Args:
        plan_id: ID плана для проверки
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not plan_id:
        return False, "ID плана не может быть пустым"
    if plan_id not in PLANS_DICT:
        return False, f"План с ID '{plan_id}' не существует"
    plan = PLANS_DICT[plan_id]
    required_fields = ['name', 'price', 'duration_days']
    for field in required_fields:
        if field not in plan:
            return False, f"План '{plan_id}' содержит некорректные данные (отсутствует {field})"
    try:
        price = float(plan['price'])
        days = int(plan['duration_days'])
        if price <= 0:
            return False, f"План '{plan_id}' имеет некорректную цену"
        if days <= 0:
            return False, f"План '{plan_id}' имеет некорректное количество дней"
    except (ValueError, TypeError):
        return False, f"План '{plan_id}' содержит некорректные числовые данные"
    return True, ""

def validate_file_type(file_name: str, allowed_types: list = None) -> tuple[bool, str]:
    """
    Валидация типа файла по расширению
    
    Args:
        file_name: Имя файла
        allowed_types: Список разрешенных расширений
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not file_name:
        return False, "Имя файла не может быть пустым"
    
    if allowed_types is None:
        allowed_types = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx']
    
    # Получаем расширение файла
    file_extension = file_name.lower().split('.')[-1] if '.' in file_name else ''
    
    if not file_extension:
        return False, "Файл должен иметь расширение"
    
    if file_extension not in [ext.lower() for ext in allowed_types]:
        return False, f"Неподдерживаемый тип файла. Разрешены: {', '.join(allowed_types)}"
    
    return True, ""

def validate_date_range(start_date: str, end_date: str) -> tuple[bool, str]:
    """
    Валидация диапазона дат
    
    Args:
        start_date: Начальная дата (ISO формат)
        end_date: Конечная дата (ISO формат)
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        return False, "Неверный формат даты (ожидается ISO формат)"
    
    if start >= end:
        return False, "Начальная дата должна быть раньше конечной"
    
    # Проверяем разумность диапазона (не более 1 года)
    if (end - start).days > 365:
        return False, "Диапазон дат не может превышать 1 год"
    
    return True, ""

def validate_traffic_limit(limit_gb: Union[str, int, float]) -> tuple[bool, str]:
    """
    Валидация лимита трафика в ГБ
    
    Args:
        limit_gb: Лимит трафика в ГБ
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        limit = float(limit_gb)
    except (ValueError, TypeError):
        return False, "Лимит трафика должен быть числом"
    
    if limit < 0:
        return False, "Лимит трафика не может быть отрицательным"
    
    if limit > 1000:  # Более 1TB кажется нереальным
        return False, "Лимит трафика слишком большой (максимум 1000 ГБ)"
    
    # Проверка на разумные значения (не более 2 знаков после запятой)
    if round(limit, 2) != limit:
        return False, "Лимит трафика не может содержать более 2 знаков после запятой"
    
    return True, ""

def validate_subscription_days(days: Union[str, int]) -> tuple[bool, str]:
    """
    Валидация количества дней подписки
    
    Args:
        days: Количество дней
        
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        days_int = int(days)
    except (ValueError, TypeError):
        return False, "Количество дней должно быть целым числом"
    
    if days_int <= 0:
        return False, "Количество дней должно быть положительным"
    
    max_days = config.LIMITS.get('max_subscription_days', 365)
    if days_int > max_days:
        return False, f"Максимальный период подписки: {max_days} дней"
    
    return True, ""

def sanitize_input(text: str, max_length: int = 1000) -> str:
    """
    Очистка пользовательского ввода от потенциально опасных символов
    
    Args:
        text: Текст для очистки
        max_length: Максимальная длина текста
        
    Returns:
        str: Очищенный текст
    """
    if not text:
        return ""
    
    # Удаляем потенциально опасные символы
    dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\r']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    # Ограничиваем длину
    text = text[:max_length]
    
    # Убираем лишние пробелы
    text = ' '.join(text.split())
    
    return text.strip()

def validate_comment(comment: str) -> tuple[bool, str]:
    """
    Валидация комментария (для платежей, примечаний и т.д.)
    
    Args:
        comment: Комментарий для проверки
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not comment:
        return True, ""  # Комментарий может быть пустым
    
    comment = comment.strip()
    
    # Проверка длины
    if len(comment) > 500:
        return False, "Комментарий не может содержать более 500 символов"
    
    # Проверка на недопустимые символы
    if re.search(r'[<>"\']', comment):
        return False, "Комментарий содержит недопустимые символы"
    
    return True, ""

# Вспомогательные функции для удобства
def is_valid_username(username: str) -> bool:
    """Быстрая проверка валидности имени пользователя"""
    valid, _ = validate_username(username)
    return valid

def is_valid_telegram_id(telegram_id: Union[str, int]) -> bool:
    """Быстрая проверка валидности Telegram ID"""
    valid, _ = validate_telegram_id(telegram_id)
    return valid

def is_valid_amount(amount: Union[str, int, float]) -> bool:
    """Быстрая проверка валидности суммы"""
    valid, _ = validate_payment_amount(amount)
    return valid

def clean_phone_number(phone: str) -> str:
    """Очистка номера телефона от лишних символов"""
    if not phone:
        return ""
    
    # Удаляем все кроме цифр и +
    cleaned = re.sub(r'[^\d+]', '', phone.strip())
    
    # Если номер начинается с 8, заменяем на +7 (для России)
    if cleaned.startswith('8') and len(cleaned) == 11:
        cleaned = '+7' + cleaned[1:]
    elif cleaned.startswith('7') and len(cleaned) == 11:
        cleaned = '+' + cleaned
    
    return cleaned

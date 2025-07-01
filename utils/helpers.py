import hashlib
import secrets
import string
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import asyncio
from texts import get_json

logger = logging.getLogger(__name__)

def generate_invite_code(username: str, timestamp: Optional[int] = None) -> str:
    """
    Генерация кода приглашения для связывания аккаунта
    
    Args:
        username: Имя пользователя
        timestamp: Временная метка (опционально)
        
    Returns:
        str: Код приглашения в формате link_username_hash
    """
    if timestamp is None:
        timestamp = int(datetime.now().timestamp())
    
    # Создаем хеш для уникальности
    hash_source = f"{username}_{timestamp}_{secrets.token_hex(8)}"
    hash_value = hashlib.md5(hash_source.encode()).hexdigest()[:6]
    
    return f"link_{username}_{hash_value}"

def generate_transaction_id(prefix: str = "tx") -> str:
    """
    Генерация уникального ID транзакции
    
    Args:
        prefix: Префикс для ID
        
    Returns:
        str: Уникальный ID транзакции
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = secrets.token_hex(4)
    return f"{prefix}_{timestamp}_{random_part}"

def format_currency(amount: float, currency: str = "руб.") -> str:
    """
    Форматирование суммы с валютой
    
    Args:
        amount: Сумма
        currency: Валюта
        
    Returns:
        str: Отформатированная строка
    """
    return f"{amount:,.2f} {currency}".replace(",", " ")

def format_duration(days: int) -> str:
    """
    Форматирование длительности в человекочитаемом виде
    
    Args:
        days: Количество дней
        
    Returns:
        str: Отформатированная строка
    """
    if days == 1:
        return "1 день"
    elif days < 5:
        return f"{days} дня"
    elif days < 21:
        return f"{days} дней"
    elif days == 30:
        return "1 месяц"
    elif days == 90:
        return "3 месяца"
    elif days == 180:
        return "6 месяцев"
    elif days == 365:
        return "1 год"
    else:
        months = days // 30
        if months > 1:
            return f"{months} месяцев"
        else:
            return f"{days} дней"

def format_file_size(size_bytes: int) -> str:
    """
    Форматирование размера файла в человекочитаемом виде
    
    Args:
        size_bytes: Размер в байтах
        
    Returns:
        str: Отформатированный размер
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

def calculate_discount(original_price: float, discount_percent: float) -> tuple[float, float]:
    """
    Расчет скидки
    
    Args:
        original_price: Первоначальная цена
        discount_percent: Процент скидки
        
    Returns:
        tuple: (новая цена, размер скидки)
    """
    discount_amount = original_price * (discount_percent / 100)
    new_price = original_price - discount_amount
    return new_price, discount_amount

def generate_secure_password(length: int = 12) -> str:
    """
    Генерация безопасного пароля
    
    Args:
        length: Длина пароля
        
    Returns:
        str: Сгенерированный пароль
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password

def mask_sensitive_data(data: str, visible_chars: int = 4) -> str:
    """
    Маскировка чувствительных данных
    
    Args:
        data: Данные для маскировки
        visible_chars: Количество видимых символов с каждой стороны
        
    Returns:
        str: Замаскированные данные
    """
    if len(data) <= visible_chars * 2:
        return "*" * len(data)
    
    start = data[:visible_chars]
    end = data[-visible_chars:]
    middle = "*" * (len(data) - visible_chars * 2)
    
    return f"{start}{middle}{end}"

def get_time_until_expiry(expire_timestamp: int) -> Dict[str, Any]:
    """
    Получение времени до истечения подписки
    
    Args:
        expire_timestamp: Временная метка истечения
        
    Returns:
        dict: Информация о времени до истечения
    """
    now = datetime.now()
    expire_date = datetime.fromtimestamp(expire_timestamp)
    
    if expire_date <= now:
        return {
            "is_expired": True,
            "days_remaining": 0,
            "hours_remaining": 0,
            "time_left": "Истекла"
        }
    
    time_diff = expire_date - now
    days = time_diff.days
    hours = time_diff.seconds // 3600
    
    if days > 0:
        time_left = f"{days} дн."
    elif hours > 0:
        time_left = f"{hours} ч."
    else:
        minutes = (time_diff.seconds % 3600) // 60
        time_left = f"{minutes} мин."
    
    return {
        "is_expired": False,
        "days_remaining": days,
        "hours_remaining": hours,
        "time_left": time_left,
        "expire_date": expire_date
    }

def check_file_type(filename: str) -> Dict[str, Any]:
    """
    Определение типа файла и его свойств
    
    Args:
        filename: Имя файла
        
    Returns:
        dict: Информация о файле
    """
    if not filename:
        return {"is_valid": False, "error": "Имя файла пустое"}
    
    # Извлекаем расширение
    extension = filename.lower().split('.')[-1] if '.' in filename else ''
    
    # Определяем тип файла
    image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
    document_extensions = ['pdf', 'doc', 'docx', 'txt', 'rtf']
    
    if extension in image_extensions:
        file_type = "image"
        is_receipt = True  # Изображения обычно чеки
    elif extension in document_extensions:
        file_type = "document"
        is_receipt = True  # Документы тоже могут быть чеками
    else:
        file_type = "unknown"
        is_receipt = False
    
    return {
        "is_valid": extension in image_extensions + document_extensions,
        "file_type": file_type,
        "extension": extension,
        "is_receipt": is_receipt,
        "error": None if extension in image_extensions + document_extensions else f"Неподдерживаемый тип файла: {extension}"
    }

def create_pagination_data(items: List[Any], page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """
    Создание данных для пагинации
    
    Args:
        items: Список элементов
        page: Номер страницы
        per_page: Элементов на страницу
        
    Returns:
        dict: Данные пагинации
    """
    total_items = len(items)
    total_pages = (total_items + per_page - 1) // per_page
    
    start_index = (page - 1) * per_page
    end_index = start_index + per_page
    
    page_items = items[start_index:end_index]
    
    return {
        "items": page_items,
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_items,
        "per_page": per_page,
        "has_next": page < total_pages,
        "has_prev": page > 1,
        "next_page": page + 1 if page < total_pages else None,
        "prev_page": page - 1 if page > 1 else None
    }

def calculate_subscription_price(days: int, base_price_per_month: float) -> float:
    """
    Расчет цены подписки на основе количества дней
    
    Args:
        days: Количество дней
        base_price_per_month: Базовая цена за месяц
        
    Returns:
        float: Рассчитанная цена
    """
    months = days / 30.0
    
    # Применяем скидки для длительных подписок
    if days >= 365:  # Год
        discount = 0.25  # 25% скидка
    elif days >= 180:  # Полгода
        discount = 0.15  # 15% скидка
    elif days >= 90:   # Квартал
        discount = 0.10  # 10% скидка
    else:
        discount = 0
    
    price = base_price_per_month * months
    discounted_price = price * (1 - discount)
    
    return round(discounted_price, 2)

def format_user_status(status: str) -> Dict[str, str]:
    """
    Форматирование статуса пользователя
    
    Args:
        status: Статус пользователя
        
    Returns:
        dict: Отформатированный статус с эмодзи
    """
    mappings = get_json("formatters/status_mappings.json")["user_status"]
    return mappings.get(status.lower(), mappings["unknown"])

def safe_divide(dividend: float, divisor: float, default: float = 0.0) -> float:
    """
    Безопасное деление с обработкой деления на ноль
    
    Args:
        dividend: Делимое
        divisor: Делитель
        default: Значение по умолчанию при делении на ноль
        
    Returns:
        float: Результат деления
    """
    try:
        if divisor == 0:
            return default
        return dividend / divisor
    except (TypeError, ZeroDivisionError):
        return default

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Обрезка текста с добавлением суффикса
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        suffix: Суффикс для обрезанного текста
        
    Returns:
        str: Обрезанный текст
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def extract_numbers_from_text(text: str) -> List[float]:
    """
    Извлечение всех чисел из текста
    
    Args:
        text: Текст для анализа
        
    Returns:
        list: Список найденных чисел
    """
    import re
    
    if not text:
        return []
    
    # Ищем числа (включая дробные)
    pattern = r'-?\d+(?:\.\d+)?'
    matches = re.findall(pattern, text)
    
    numbers = []
    for match in matches:
        try:
            numbers.append(float(match))
        except ValueError:
            continue
    
    return numbers

def is_business_hours(timezone_offset: int = 3) -> bool:
    """
    Проверка, является ли текущее время рабочим
    
    Args:
        timezone_offset: Смещение часового пояса от UTC
        
    Returns:
        bool: True если рабочее время
    """
    from datetime import datetime, timezone, timedelta
    
    # Получаем текущее время в указанном часовом поясе
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)
    
    # Рабочие часы: 9:00 - 21:00, понедельник - пятница
    if now.weekday() >= 5:  # Суббота (5) или воскресенье (6)
        return False
    
    if now.hour < 9 or now.hour >= 21:
        return False
    
    return True

def get_next_business_day(timezone_offset: int = 3) -> datetime:
    """
    Получение следующего рабочего дня
    
    Args:
        timezone_offset: Смещение часового пояса от UTC
        
    Returns:
        datetime: Дата следующего рабочего дня
    """
    from datetime import datetime, timezone, timedelta
    
    tz = timezone(timedelta(hours=timezone_offset))
    now = datetime.now(tz)
    
    # Начинаем с завтрашнего дня
    next_day = now + timedelta(days=1)
    
    # Ищем следующий рабочий день (понедельник-пятница)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    
    # Устанавливаем время начала рабочего дня (9:00)
    next_business_day = next_day.replace(hour=9, minute=0, second=0, microsecond=0)
    
    return next_business_day

async def retry_async(func, max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Повторное выполнение асинхронной функции с экспоненциальной задержкой
    
    Args:
        func: Асинхронная функция для выполнения
        max_attempts: Максимальное количество попыток
        delay: Начальная задержка в секундах
        backoff: Коэффициент увеличения задержки
        
    Returns:
        Результат выполнения функции
        
    Raises:
        Exception: Последнее исключение, если все попытки неудачны
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return func()
        except Exception as e:
            last_exception = e
            logger.warning(f"Попытка {attempt + 1} неудачна: {e}")
            
            if attempt < max_attempts - 1:
                await asyncio.sleep(current_delay)
                current_delay *= backoff
    
    raise last_exception

def clean_html_tags(text: str) -> str:
    """
    Удаление HTML тегов из текста
    
    Args:
        text: Текст с HTML тегами
        
    Returns:
        str: Очищенный текст
    """
    import re
    
    if not text:
        return ""
    
    # Удаляем HTML теги
    clean_text = re.sub(r'<[^>]+>', '', text)
    
    # Заменяем HTML сущности
    html_entities = {
        '&lt;': '<',
        '&gt;': '>',
        '&amp;': '&',
        '&quot;': '"',
        '&#39;': "'",
        '&nbsp;': ' '
    }
    
    for entity, char in html_entities.items():
        clean_text = clean_text.replace(entity, char)
    
    return clean_text.strip()

def generate_qr_data(url: str, username: str) -> Dict[str, str]:
    """
    Генерация данных для QR кода
    
    Args:
        url: URL для подписки
        username: Имя пользователя
        
    Returns:
        dict: Данные для QR кода
    """
    return {
        "url": url,
        "username": username,
        "generated_at": datetime.now().isoformat(),
        "type": "subscription"
    }

def validate_subscription_url(url: str) -> Dict[str, Any]:
    """
    Валидация и анализ URL подписки
    
    Args:
        url: URL для проверки
        
    Returns:
        dict: Результат валидации
    """
    import re
    from urllib.parse import urlparse
    
    if not url:
        return {"is_valid": False, "error": "URL не может быть пустым"}
    
    try:
        parsed = urlparse(url)
        
        # Проверяем базовую структуру URL
        if not parsed.scheme or not parsed.netloc:
            return {"is_valid": False, "error": "Неверная структура URL"}
        
        # Проверяем протокол
        if parsed.scheme not in ['http', 'https']:
            return {"is_valid": False, "error": "Поддерживаются только HTTP и HTTPS"}
        
        # Определяем тип URL подписки
        path = parsed.path.lower()
        url_type = "unknown"
        
        if '/sub/' in path:
            url_type = "standard"
        elif '/subscription/' in path:
            url_type = "subscription"
        elif '/api/sub' in path:
            url_type = "api"
        
        return {
            "is_valid": True,
            "url_type": url_type,
            "domain": parsed.netloc,
            "path": parsed.path,
            "scheme": parsed.scheme,
            "error": None
        }
        
    except Exception as e:
        return {"is_valid": False, "error": f"Ошибка парсинга URL: {str(e)}"}

def calculate_usage_percentage(used: int, total: int) -> float:
    """
    Расчет процента использования
    
    Args:
        used: Использовано
        total: Общее количество
        
    Returns:
        float: Процент использования (0-100)
    """
    if total <= 0:
        return 0.0
    
    percentage = (used / total) * 100
    return min(100.0, max(0.0, percentage))

def format_remaining_time(days: int, hours: int = 0) -> str:
    """
    Форматирование оставшегося времени
    
    Args:
        days: Количество дней
        hours: Количество часов
        
    Returns:
        str: Отформатированное время
    """
    if days > 30:
        months = days // 30
        remaining_days = days % 30
        if remaining_days > 0:
            return f"{months} мес. {remaining_days} дн."
        else:
            return f"{months} мес."
    elif days > 0:
        if hours > 0:
            return f"{days} дн. {hours} ч."
        else:
            return f"{days} дн."
    elif hours > 0:
        return f"{hours} ч."
    else:
        return "Менее часа"

def get_traffic_warning_level(used_percentage: float) -> Dict[str, Any]:
    """
    Определение уровня предупреждения по использованию трафика
    
    Args:
        used_percentage: Процент использования (0-100)
        
    Returns:
        dict: Информация об уровне предупреждения
    """
    if used_percentage >= 95:
        return {
            "level": "critical",
            "emoji": "🔴",
            "message": "Трафик почти закончился!",
            "color": "#FF0000"
        }
    elif used_percentage >= 80:
        return {
            "level": "warning",
            "emoji": "🟡",
            "message": "Трафик заканчивается",
            "color": "#FFA500"
        }
    elif used_percentage >= 60:
        return {
            "level": "info",
            "emoji": "🔵",
            "message": "Больше половины трафика использовано",
            "color": "#0080FF"
        }
    else:
        return {
            "level": "ok",
            "emoji": "🟢",
            "message": "Трафик в норме",
            "color": "#008000"
        }

def create_backup_filename(prefix: str = "backup") -> str:
    """
    Создание имени файла для резервной копии
    
    Args:
        prefix: Префикс имени файла
        
    Returns:
        str: Имя файла для резервной копии
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.db"

def log_user_action(user_id: int, action: str, details: Dict[str, Any] = None):
    """
    Логирование действий пользователя
    
    Args:
        user_id: ID пользователя
        action: Действие
        details: Дополнительные детали
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details or {}
    }
    
    logger.info(f"User action: {log_entry}")

def estimate_processing_time(queue_length: int, avg_processing_time: float = 30.0) -> str:
    """
    Оценка времени обработки заявки
    
    Args:
        queue_length: Длина очереди
        avg_processing_time: Среднее время обработки в минутах
        
    Returns:
        str: Оценка времени
    """
    total_minutes = queue_length * avg_processing_time
    
    if total_minutes < 60:
        return f"около {int(total_minutes)} минут"
    elif total_minutes < 1440:  # меньше суток
        hours = int(total_minutes // 60)
        return f"около {hours} часов"
    else:
        days = int(total_minutes // 1440)
        return f"около {days} дней"

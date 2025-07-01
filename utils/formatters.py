from datetime import datetime
from telegram import InlineKeyboardButton
from typing import Dict, List, Any, Optional
import html
import logging
from texts import TextManager, get_json

def escape_html(text: str) -> str:
    """Экранирование HTML символов"""
    if text is None:
        return ""
    return html.escape(str(text))

def format_welcome_message(first_name: str, user: Dict) -> str:
    """Форматирование приветственного сообщения для связанного пользователя (без HTML-тегов)"""
    safe_name = escape_html(first_name)
    safe_username = escape_html(user['marzban_username'])
    status = '✅ Активен' if user.get('is_verified') else '❌ Не активен'
    
    return get_json("formatters.status_messages")["welcome_message"].format(
        first_name=safe_name,
        username=safe_username,
        status=status
    )

def format_status_message(stats: Dict, username: str, marzban_api) -> tuple:
    """Форматирование сообщения о статусе пользователя"""
    if not stats:
        return "❌ Ошибка получения статистики", []
    
    messages = get_json("formatters/status_messages.json")
    safe_username = escape_html(username)
    status = escape_html(stats.get('status', 'unknown')).upper()
    
    message = messages["status_header"]
    message += messages["user_info"].format(
        username=safe_username,
        status_emoji=_get_status_emoji(stats['status']),
        status=status
    )
    
    # Информация о трафике
    if stats['data_limit_bytes'] > 0:
        used_gb = stats['used_traffic_gb']
        limit_gb = stats['data_limit_gb']
        percentage = stats['traffic_percentage']
        message += messages["traffic_info"]["limited"].format(
            used_gb=f"{used_gb:.2f}",
            limit_gb=f"{limit_gb:.1f}",
            percentage=f"{percentage:.1f}",
            progress_bar=_get_progress_bar(percentage)
        )
    else:
        message += messages["traffic_info"]["unlimited"].format(
            used_gb=f"{stats['used_traffic_gb']:.2f}"
        )
    
    # Информация о сроке действия
    if stats['expire_timestamp']:
        expire_date = datetime.fromtimestamp(stats['expire_timestamp'])
        formatted_date = expire_date.strftime('%d.%m.%Y')
        
        if stats['is_expired']:
            message += messages["subscription_info"]["expired"].format(expire_date=formatted_date)
        else:
            days_left = stats['days_remaining']
            message_key = "active_warning" if days_left <= 3 else "active_normal"
            message += messages["subscription_info"][message_key].format(
                expire_date=formatted_date,
                days_left=days_left
            )
    else:
        message += messages["subscription_info"]["unlimited"]
    
    # Кнопки
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить", callback_data="status")],
        [InlineKeyboardButton("🔗 Получить ссылку", callback_data=f"get_subscription_{username}")],
        [InlineKeyboardButton("💳 Продлить подписку", callback_data="payment")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
    ]
    
    return message, keyboard

def format_user_info_message(user: Dict, stats: Dict, marzban_api) -> str:
    """Форматирование информации о пользователе для админов (MarkdownV2, без HTML)"""
    def esc(text):
        if not text:
            return '-'
        return str(text).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')

    safe_username = esc(user['marzban_username'])
    message = f"👤 *ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ*\n\n"
    message += f"🔐 Username: `{safe_username}`\n"
    if user.get('telegram_id'):
        message += f"📱 Telegram ID: `{esc(user['telegram_id'])}`\n"
    if user.get('telegram_username'):
        message += f"📱 Telegram: @{esc(user['telegram_username'])}\n"
    reg_date = esc(user.get('registration_date', 'N/A'))
    message += f"📅 Регистрация: {reg_date}\n"
    message += f"✅ Верифицирован: {'Да' if user.get('is_verified') else 'Нет'}\n\n"
    # Статистика из Marzban
    if stats:
        status = esc(stats.get('status', 'unknown')).upper()
        message += f"📊 *СТАТИСТИКА MARZBAN:*\n"
        message += f"📈 Статус: {status}\n"
        # Трафик
        if stats['data_limit_bytes'] > 0:
            message += f"📊 Трафик: {stats['used_traffic_gb']:.2f}/{stats['data_limit_gb']:.1f} ГБ ({stats['traffic_percentage']:.1f}%)\n"
        else:
            message += f"📊 Трафик: {stats['used_traffic_gb']:.2f} ГБ (безлимит)\n"
        # Срок действия
        if stats['expire_timestamp']:
            expire_date = datetime.fromtimestamp(stats['expire_timestamp'])
            formatted_date = expire_date.strftime('%d\.%m\.%Y')
            status_text = "❌ Истекла" if stats['is_expired'] else f"✅ {stats['days_remaining']} дней"
            message += f"📅 Подписка: {status_text} (до {formatted_date})\n"
        else:
            message += f"📅 Подписка: Бессрочная\n"
    else:
        message += f"❌ Не удалось получить статистику из Marzban\n"
    # Примечания
    if user.get('notes'):
        safe_notes = esc(user['notes'])
        message += f"\n📝 *ПРИМЕЧАНИЯ:*\n{safe_notes}\n"
    # Платежи
    payments = user.get('payments')
    if payments:
        message += "\n💰 *ПОСЛЕДНИЕ ПЛАТЕЖИ:*\n"
        for p in payments:
            # p = {'date': ..., 'amount': ..., 'status': ..., 'time': ...}
            pay_date = esc(p.get('date', '-'))
            pay_time = esc(p.get('time', '-'))
            pay_amount = esc(p.get('amount', '-'))
            pay_status = esc(p.get('status', '-'))
            # Если time нет, пробуем взять из date (если там есть время)
            if pay_time == '-' and pay_date != '-':
                # Попробуем распарсить дату и время
                try:
                    dt = datetime.fromisoformat(p['date'])
                    pay_date = dt.strftime('%d.%m.%Y')
                    pay_time = dt.strftime('%H:%M')
                except Exception:
                    pass
            message += f"• {pay_date} {pay_time}: {pay_amount} руб. ({pay_status})\n"
    return message

def format_statistics_message(stats: Dict) -> str:
    """Форматирование общей статистики системы (без HTML-тегов)"""
    message = f"📊 СТАТИСТИКА СИСТЕМЫ\n\n"
    
    # Пользователи
    message += f"👥 ПОЛЬЗОВАТЕЛИ:\n"
    message += f"Всего: {stats.get('total_users', 0)}\n"
    message += f"Связанных с Telegram: {stats.get('linked_users', 0)}\n"
    message += f"Активных: {stats.get('active_users', 0)}\n"
    message += f"Новых за 24ч: {stats.get('new_users_24h', 0)}\n\n"
    
    # Платежи
    message += f"💰 ПЛАТЕЖИ:\n"
    message += f"Ожидающих: {stats.get('pending_payments', 0)}\n"
    message += f"Одобренных сегодня: {stats.get('approved_today', 0)}\n"
    message += f"Доход за месяц: {stats.get('monthly_revenue', 0)} руб.\n\n"
    
    # Система
    message += f"⚙️ СИСТЕМА:\n"
    uptime = stats.get('uptime', 'N/A')
    message += f"Время работы: {uptime}\n"
    
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
    message += f"Последнее обновление: {current_time}"
    
    return message

def format_pending_payments_message(requests: List[Dict]) -> str:
    """Форматирование списка ожидающих заявок (без HTML-тегов)"""
    if not requests:
        return "✅ Нет ожидающих заявок на оплату."
    
    message = f"💰 ОЖИДАЮЩИЕ ЗАЯВКИ ({len(requests)}):\n\n"
    
    for req in requests[:10]:  # Показываем максимум 10 заявок
        created_date = datetime.fromisoformat(req['created_at']).strftime('%d.%m %H:%M')
        safe_username = escape_html(req['marzban_username'])
        safe_plan_id = escape_html(req['plan_id'])
        
        message += f"🆔 Заявка #{req['id']}\n"
        message += f"👤 {safe_username}\n"
        message += f"💰 {req['amount']} руб. ({safe_plan_id})\n"
        message += f"📅 {created_date}\n"
        message += f"📎 Чек: {'✅' if req.get('receipt_file_id') else '❌'}\n"
        message += f"/approve {req['id']} | /reject {req['id']} причина\n\n"
    
    if len(requests) > 10:
        message += f"... и еще {len(requests) - 10} заявок\n"
    
    return message

def format_admin_notification(username: str, telegram_id: int, telegram_username: str, trial_days: int) -> str:
    """Форматирование уведомления админам о новой регистрации"""
    safe_username = escape_html(username)
    current_time = datetime.now().strftime('%d.%m.%Y %H:%M')
    
    message = f"🆕 <b>НОВАЯ РЕГИСТРАЦИЯ</b>\n\n"
    message += f"👤 Пользователь: <code>{safe_username}</code>\n"
    
    if telegram_username:
        safe_tg_username = escape_html(telegram_username)
        message += f"📱 Telegram: @{safe_tg_username} (ID: {telegram_id})\n"
    else:
        message += f"📱 Telegram ID: {telegram_id}\n"
    
    message += f"📅 Пробный период: {trial_days} дней\n"
    message += f"🕐 Время: {current_time}\n\n"
    
    # Добавляем ссылки для быстрых действий
    message += f"🔧 <b>Быстрые команды:</b>\n"
    message += f"<code>/user_info {username}</code> - информация\n"
    message += f"<code>/test_subscription {username}</code> - тест ссылки\n"
    message += f"<code>/subscription {username}</code> - получить ссылку"
    
    return message

def _get_status_emoji(status: str) -> str:
    """Получение эмодзи для статуса"""
    status_map = {
        'active': '✅',
        'disabled': '❌',
        'expired': '🚫',
        'limited': '⚠️'
    }
    return status_map.get(status.lower(), '❓')

def _get_progress_bar(percentage: float, length: int = 10) -> str:
    """Создание прогресс-бара"""
    filled = int(percentage / 100 * length)
    empty = length - filled
    
    if percentage >= 90:
        bar = '🔴' * filled + '⚪' * empty
    elif percentage >= 70:
        bar = '🟡' * filled + '⚪' * empty
    else:
        bar = '🟢' * filled + '⚪' * empty
    
    return f"{bar} {percentage:.1f}%"

def format_connection_info_message(username: str, connection_info: Dict) -> str:
    """Форматирование информации для подключения"""
    safe_username = escape_html(username)
    
    message = f"🔗 <b>ДАННЫЕ ДЛЯ ПОДКЛЮЧЕНИЯ</b>\n\n"
    message += f"👤 Пользователь: <code>{safe_username}</code>\n"
    
    if connection_info.get('status'):
        status = escape_html(connection_info['status']).upper()
        message += f"📊 Статус: {_get_status_emoji(connection_info['status'])} {status}\n"
    
    if connection_info.get('protocols'):
        protocols_text = ', '.join(connection_info['protocols'])
        message += f"🔧 Протоколы: {protocols_text}\n"
    
    message += "\n"
    
    # Основная ссылка подписки
    if connection_info.get('subscription_url'):
        safe_url = escape_html(connection_info['subscription_url'])
        message += f"📋 <b>Ссылка подписки:</b>\n<code>{safe_url}</code>\n\n"
    
    # Дополнительные форматы
    if connection_info.get('clash_url'):
        safe_clash_url = escape_html(connection_info['clash_url'])
        message += f"⚡ <b>Для Clash:</b>\n<code>{safe_clash_url}</code>\n\n"
    
    if connection_info.get('v2ray_url'):
        safe_v2ray_url = escape_html(connection_info['v2ray_url'])
        message += f"🚀 <b>Для V2Ray:</b>\n<code>{safe_v2ray_url}</code>\n\n"
    
    # Инструкция
    message += f"📱 <b>Инструкция:</b>\n"
    message += f"1. Скопируйте ссылку подписки выше\n"
    message += f"2. Откройте ваше VPN приложение\n"
    message += f"3. Найдите раздел 'Подписки' или 'Import'\n"
    message += f"4. Вставьте ссылку и обновите серверы\n"
    message += f"5. Выберите сервер и подключайтесь!"
    
    return message

def determine_user_status(user_data: dict) -> str:
    """Определение статуса пользователя Marzban"""
    if not user_data.get('status') == 'active':
        return 'Отключен'
    expire_timestamp = user_data.get('expire')
    if expire_timestamp:
        expire_date = datetime.fromtimestamp(expire_timestamp)
        if expire_date < datetime.now():
            return 'Истек срок действия'
    data_limit = user_data.get('data_limit', 0)
    used_traffic = user_data.get('used_traffic', 0)
    if data_limit and used_traffic >= data_limit:
        return 'Превышен лимит трафика'
    return 'Активен'

def format_timestamp(timestamp: Optional[int]) -> str:
    """Форматирование временной метки"""
    formats = get_json("formatters/datetime_formats.json")["timestamp_formats"]
    
    if not timestamp:
        return formats["not_set"]
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime(formats["default"])
    except Exception:
        return formats["invalid"]

def format_bytes(bytes_value: Optional[int]) -> str:
    if not bytes_value:
        return '0 B'
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.2f} PB"

# Дополнительные функции для совместимости
def format_payment_plans_message() -> tuple:
    """Форматирование сообщения с планами подписки"""
    return "Используйте PaymentHandlers.show_payment_plans()", []

def format_payment_details_message(plan: Dict, user: Dict) -> tuple:
    """Форматирование деталей платежа"""
    return "Используйте PaymentHandlers.process_payment_plan()", []

def escape_markdown_v2(text: str) -> str:
    """
    Экранирование специальных символов для Telegram MarkdownV2.
    Централизованная функция для всего проекта.
    """
    if text is None:
        return "-"
    
    # Конвертируем в строку если это не строка
    text = str(text)
    
    # Экранируем все зарезервированные символы для MarkdownV2
    # Порядок важен! Сначала экранируем обратный слэш, затем остальные символы
    text = text.replace('\\', '\\\\')  # Сначала экранируем сам слэш
    
    # Все специальные символы MarkdownV2
    special_chars = '_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text
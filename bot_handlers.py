from texts import get_text
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
user_states = {}
config = ... # инициализация вашей конфигурации, например get_config()

async def _process_username_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода логина при регистрации"""
    user_id = update.effective_user.id
    username = update.message.text.strip()
    
    # Валидация логина
    if not self._validate_username(username):
        await update.message.reply_text(
            get_text("messages.errors.INVALID_USERNAME", min_len=config.NEW_USER_SETTINGS['username_min_length'], max_len=config.NEW_USER_SETTINGS['username_max_length'])
        )
        return
    
    # Проверяем доступность логина
    if not self.marzban.check_username_availability(username):
        await update.message.reply_text(
            get_text("messages.errors.USERNAME_TAKEN", username=username)
        )
        return
    
    # Создаем пользователя в Marzban
    await update.message.reply_text(get_text("user.registration.ACCOUNT_CREATING"))
    
    trial_days = config.NEW_USER_SETTINGS.get('trial_days', 3)
    protocols = config.NEW_USER_SETTINGS.get('default_protocols', ['vless'])
    data_limit = config.NEW_USER_SETTINGS.get('data_limit_gb')
    
    success = self.marzban.create_new_user(
        username=username,
        protocols=protocols,
        trial_days=trial_days,
        data_limit_gb=data_limit
    )
    
    if not success:
        await update.message.reply_text(get_text("messages.errors.ACCOUNT_CREATION_ERROR"))
        # Очищаем состояние
        del user_states[user_id]
        return
    
    # Создаем запись в базе данных бота
    db_success = self.db.create_new_user_record(
        username=username,
        telegram_id=user_id,
        telegram_username=update.effective_user.username
    )
    
    if not db_success:
        logger.error(f"Не удалось создать запись в БД для {username}")
    
    # Синхронизируем с Marzban примечания
    self.marzban.sync_telegram_id_to_marzban_notes(
        username, user_id, update.effective_user.username
    )
    
    # Очищаем состояние
    del user_states[user_id]
    
    # Отправляем приветственное сообщение
    welcome_message = get_text("user.registration.ACCOUNT_CREATED", username=username, trial_days=trial_days)
    
    # Создаем кнопки главного меню
    keyboard = [
        [InlineKeyboardButton("📱 Скачать приложение", callback_data="download_app")],
        [InlineKeyboardButton("📊 Статус подписки", callback_data="status")],
        [InlineKeyboardButton("🔗 Получить ссылку подписки", callback_data=f"get_subscription_{username}")],
        [InlineKeyboardButton("💳 Продлить подписку", callback_data="payment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    
    # Получаем и отправляем правильную ссылку для подключения
    connection_info = self.marzban.get_user_connection_info(username)
    
    if connection_info and connection_info.get('subscription_url'):
        # Проверяем, работает ли ссылка
        subscription_url = connection_info['subscription_url']
        
        # Простая проверка доступности ссылки
        try:
            import requests
            test_response = requests.head(subscription_url, timeout=5)
            url_status = "✅ Проверена" if test_response.status_code == 200 else "⚠️ Требует проверки"
        except:
            url_status = "⚠️ Требует проверки"
        
        connection_message = get_text("user.subscription.CONNECTION_MESSAGE", username=username, url_status=url_status, subscription_url=subscription_url, clash_url=connection_info.get('clash_url', ''))
        await update.message.reply_text(connection_message, parse_mode='Markdown')
    else:
        fallback_message = get_text("user.subscription.CONNECTION_FALLBACK", username=username, marzban_url=config.MARZBAN_URL)
        await update.message.reply_text(fallback_message, parse_mode='Markdown')
    
    # Уведомляем администраторов о новой регистрации
    if config.ADMIN_NOTIFICATIONS.get("new_user_registration", True):
        admin_message = get_text("admin.ADMIN_NEW_USER_MESSAGE", username=username, telegram_username=update.effective_user.username or 'N/A', user_id=user_id, trial_days=trial_days, now=datetime.now().strftime('%d.%m.%Y %H:%M'))
        for admin_id in config.ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode='Markdown')
            except Exception as e:
                logger.error(get_text("admin.ADMIN_NOTIFICATION_ERROR", admin_id=admin_id, error=e))

# Также добавьте этот обработчик колбэков для кнопки получения подписки:

async def handle_subscription_callback(self, query, username: str):
    """Обработка запроса ссылки подписки через колбэк"""
    await query.answer(get_text("user.subscription.SUBSCRIPTION_CALLBACK_LOADING"))
    
    connection_info = self.marzban.get_user_connection_info(username)
    
    if not connection_info or not connection_info.get('subscription_url'):
        await query.edit_message_text(
            get_text("user.subscription.SUBSCRIPTION_CALLBACK_ERROR", username=username)
        )
        return
    
    subscription_url = connection_info['subscription_url']
    
    message = get_text("user.subscription.SUBSCRIPTION_CALLBACK_MESSAGE", username=username, subscription_url=subscription_url)
    
    keyboard = [
        [get_text("user.subscription.SUBSCRIPTION_BACK_BUTTON")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

async def button_callback(self, query):
    if query.data.startswith("get_subscription_"):
        username = query.data.replace("get_subscription_", "")
        await self.handle_subscription_callback(query, username)
    elif query.data.startswith("test_sub_"):
        username = query.data.replace("test_sub_", "")
        await query.answer(get_text("user.subscription.SUBSCRIPTION_CALLBACK_LOADING"))
        test_results = self.marzban.test_subscription_url(username)
        working_count = sum(1 for result in test_results.values() if result.get('works', False))
        if working_count > 0:
            await query.answer(get_text("user.subscription.TEST_SUBSCRIPTION_FOUND", count=working_count), show_alert=True)
        else:
            await query.answer(get_text("user.subscription.TEST_SUBSCRIPTION_NOT_FOUND"), show_alert=True)
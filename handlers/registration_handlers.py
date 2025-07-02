import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .base_handler import BaseHandler
from utils.formatters import format_admin_notification
from texts import get_json, get_text

class RegistrationHandlers(BaseHandler):
    """Обработчики регистрации новых пользователей"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ИСПРАВЛЕНО: Используем правильный ключ для доступа к текстам
        self.messages = get_json("handlers.registration_messages")
        import logging
        logging.getLogger(__name__).info(f"Loaded registration messages: {self.messages}")
    
    def _get_user_id(self, update):
        is_callback = hasattr(update, 'callback_query') and update.callback_query is not None
        return update.callback_query.from_user.id if is_callback else update.effective_user.id
    
    async def start_registration_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса регистрации нового пользователя"""
        telegram_id = query.from_user.id
        self.set_user_state(telegram_id, {
            'state': 'waiting_username',
            'step': 'registration'
        })
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ])
        await query.edit_message_text(
            self.messages["registration_form"], 
            reply_markup=reply_markup
        )
    
    async def link_existing_callback(self, query):
        """Инструкции по связыванию существующего аккаунта"""
        link_messages = self.messages["link_existing"]
        message = (
            link_messages["title"] +
            link_messages["instructions"] +
            link_messages["contacts"]
        )
        await query.edit_message_text(message)
    
    async def handle_text_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений (для регистрации)"""
        user_id = self._get_user_id(update)
        
        # Проверяем, находится ли пользователь в процессе регистрации
        state = self.get_user_state(user_id)
        if not state:
            return
        
        if state.get('state') == 'waiting_username' and state.get('step') == 'registration':
            await self._process_username_input(update, context)
    
    async def _process_username_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ввода логина при регистрации"""
        user_id = self._get_user_id(update)
        username = update.message.text.strip()
        
        # Валидация логина
        if not self._validate_username(username):
            validation_messages = self.messages["username_validation"]
            await update.message.reply_text(
                validation_messages["error"].format(
                    min_length=self.config.NEW_USER_SETTINGS['username_min_length'],
                    max_length=self.config.NEW_USER_SETTINGS['username_max_length']
                )
            )
            return
        
        # Проверяем доступность логина
        if not self.marzban.check_username_availability(username):
            await update.message.reply_text(
                self.messages["username_validation"]["taken"].format(username=username)
            )
            return
        
        # Создаем пользователя в Marzban
        creation_messages = self.messages["account_creation"]
        await update.message.reply_text(creation_messages["progress"])
        trial_days = self.config.NEW_USER_SETTINGS.get('trial_days', 3)
        protocols = self.config.NEW_USER_SETTINGS.get('default_protocols', ['vless'])
        data_limit = self.config.NEW_USER_SETTINGS.get('data_limit_gb')
        
        # ИСПРАВЛЕНО: Улучшена обработка ошибок
        success, error_text = self.marzban.create_new_user(
            username=username,
            protocols=protocols,
            trial_days=trial_days,
            data_limit_gb=data_limit
        )
        if not success:
            error_message = creation_messages["error"]
            # Показываем пользователю детальную причину ошибки, если она есть
            if error_text:
                error_message += f"\n\nПричина: {error_text}"
            await update.message.reply_text(error_message)
            self.clear_user_state(user_id)
            return
        
        # Создаем запись в базе данных бота
        db_success = self.db.create_new_user_record(
            username=username,
            telegram_id=user_id,
            telegram_username=update.effective_user.username
        )
        
        if not db_success:
            self.logger.error(f"Ошибка создания записи в БД для {username}")
        
        # Синхронизируем Telegram ID с примечаниями Marzban
        self.marzban.sync_telegram_id_to_marzban_notes(
            username, user_id, update.effective_user.username
        )
        
        # Очищаем состояние
        self.clear_user_state(user_id)
        
        # Отправляем приветственное сообщение
        await update.message.reply_text(
            creation_messages["success"].format(
                username=username,
                trial_days=trial_days
            )
        )
        
        # Отправляем информацию для подключения
        await self._send_connection_info(update, username)
        
        # Уведомляем администраторов о новой регистрации
        if self.config.ADMIN_NOTIFICATIONS.get("new_user_registration", True):
            admin_message = get_text("admin.ADMIN_NEW_USER_MESSAGE",
                username=username,
                telegram_username=update.effective_user.username or 'N/A',
                user_id=user_id,
                trial_days=trial_days,
                now=datetime.now().strftime('%d.%m.%Y %H:%M')
            )
            
            for admin_id in self.config.ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    self.logger.error(
                        get_text("admin.ADMIN_NOTIFICATION_ERROR",
                            admin_id=admin_id,
                            error=str(e)
                        )
                    )
    
    async def _send_connection_info(self, update: Update, username: str):
        """Отправка информации для подключения"""
        connection_info = self.marzban.get_user_connection_info(username)
        
        if connection_info and connection_info.get('subscription_url'):
            subscription_url = connection_info['subscription_url']
            # Используем метод из marzban для проверки URL
            url_status = "✅ Готова" if self.marzban.test_subscription_url(username) else "⚠️ Требует проверки"
            
            connection_message = self.messages["connection"]["message"].format(
                username=username,
                url_status=url_status,
                subscription_url=subscription_url,
                clash_url=connection_info.get('clash_url', '')
            )
            await update.message.reply_text(connection_message, parse_mode='Markdown')
        else:
            fallback_message = self.messages["connection"]["fallback"].format(
                username=username,
                marzban_url=self.config.MARZBAN_URL
            )
            await update.message.reply_text(fallback_message, parse_mode='Markdown')
    
    def _validate_username(self, username: str) -> bool:
        """Валидация логина пользователя"""
        settings = self.config.NEW_USER_SETTINGS
        
        # Проверка длины
        if len(username) < settings['username_min_length'] or len(username) > settings['username_max_length']:
            return False
        
        # Проверка паттерна (только латиница, цифры и _)
        pattern = settings['username_pattern']
        if not re.match(pattern, username):
            return False
        
        return True
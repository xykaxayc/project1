import logging
from abc import ABC
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from database_manager import DatabaseManager
from marzban_api import MarzbanAPI
from config import get_config
from texts import get_text

config = get_config()
logger = logging.getLogger(__name__)

# Глобальный словарь состояний пользователей
user_states = {}

class BaseHandler(ABC):
    """Базовый класс для всех обработчиков"""
    
    def __init__(self, db_manager: DatabaseManager, marzban_api: MarzbanAPI):
        self.db = db_manager
        self.marzban = marzban_api
        self.config = config
        self.logger = logger
    
    def is_admin(self, user_id: int) -> bool:
        """Проверка прав администратора"""
        return self.config.is_admin(user_id)
    
    async def require_admin(self, update: Update) -> bool:
        """Проверка прав администратора с отправкой сообщения об ошибке"""
        if not self.is_admin(update.effective_user.id):
            await update.message.reply_text(get_text("messages.errors.NO_ADMIN_RIGHTS"))
            return False
        return True
    
    async def get_verified_user(self, telegram_id: int) -> Dict[str, Any]:
        """Получение верифицированного пользователя"""
        user = self.db.get_user_by_telegram_id(telegram_id)
        if not user or not user['is_verified']:
            return None
        return user
    
    async def send_admin_notification(self, context: ContextTypes.DEFAULT_TYPE, message: str):
        """Отправка уведомления всем администраторам"""
        for admin_id in self.config.ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=message, parse_mode='Markdown')
            except Exception as e:
                self.logger.error(get_text("messages.errors.ADMIN_NOTIFICATION_ERROR", admin_id=admin_id, error=e))
    
    def create_main_menu_keyboard(self, user: Dict = None) -> InlineKeyboardMarkup:
        """Создание главного inline меню"""
        keyboard = [
            [InlineKeyboardButton("🆕 Создать аккаунт", callback_data="create_account"), InlineKeyboardButton("🔗 Связать аккаунт", callback_data="link_account")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="support"), InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
        ]
        if user and user.get('is_verified'):
            keyboard.insert(1, [InlineKeyboardButton("🔗 Ссылка подписки", callback_data=f"get_subscription_{user['marzban_username']}")])
        keyboard.append([InlineKeyboardButton("📱 Скачать приложение", callback_data="download_app")])
        return InlineKeyboardMarkup(keyboard)
    
    def create_reply_keyboard(self, user: Dict = None, is_admin: bool = False) -> ReplyKeyboardMarkup:
        """Создание постоянного нижнего меню"""
        if not user:
            keyboard = [
                ["🆕 Создать аккаунт", "🔗 Связать аккаунт"],
                ["📞 Поддержка", "ℹ️ Помощь"]
            ]
        else:
            keyboard = [
                ["📊 Мой статус", "🔗 Ссылка подписки"],
                ["💳 Оплатить", "📱 Приложения"],
                ["📞 Поддержка", "🏠 Главное меню"]
            ]
            if is_admin:
                keyboard.append(["👑 Админ панель", "📊 Статистика"])
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder=get_text("CHOOSE_ACTION_TEXT")
        )
    
    def create_admin_keyboard(self) -> ReplyKeyboardMarkup:
        """Создание админ клавиатуры"""
        keyboard = [
            ["📊 Статистика", "👥 Новые пользователи"],
            ["💰 Ожидающие платежи", "🔗 Ссылки для привязки"],
            ["🔧 Команды", "◀️ Назад"]
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder=get_text("CHOOSE_ADMIN_ACTION_TEXT")
        )
    
    async def send_message_with_keyboard(self, update: Update, text: str, user: Dict = None, 
                                       is_admin: bool = False, parse_mode: str = None,
                                       inline_keyboard: InlineKeyboardMarkup = None):
        """Отправка сообщения с нижней клавиатурой"""
        reply_keyboard = self.create_reply_keyboard(user, is_admin)
        await update.message.reply_text(
            text,
            reply_markup=reply_keyboard if not inline_keyboard else inline_keyboard,
            parse_mode=parse_mode
        )
        if inline_keyboard:
            await update.message.reply_text(
                get_text("CHOOSE_ACTION_TEXT"),
                reply_markup=reply_keyboard
            )
    
    async def edit_message_with_keyboard(self, query, text: str, user: Dict = None,
                                       is_admin: bool = False, parse_mode: str = None,
                                       inline_keyboard: InlineKeyboardMarkup = None):
        """Редактирование сообщения с сохранением клавиатуры"""
        try:
            if inline_keyboard:
                await query.edit_message_text(text, parse_mode=parse_mode, reply_markup=inline_keyboard)
            else:
                await query.edit_message_text(text, parse_mode=parse_mode)
        except Exception as e:
            self.logger.warning(f"Не удалось отредактировать сообщение: {e}")
            reply_keyboard = self.create_reply_keyboard(user, is_admin)
            await query.message.reply_text(
                text,
                parse_mode=parse_mode,
                reply_markup=inline_keyboard or reply_keyboard
            )
    
    def get_user_state(self, user_id: int) -> Dict:
        """Получение состояния пользователя"""
        return user_states.get(user_id, {})
    
    def set_user_state(self, user_id: int, state: Dict):
        """Установка состояния пользователя"""
        user_states[user_id] = state
    
    def clear_user_state(self, user_id: int):
        """Очистка состояния пользователя"""
        if user_id in user_states:
            del user_states[user_id]
    
    def _get_user_id(self, update):
        is_callback = hasattr(update, 'callback_query') and update.callback_query is not None
        return update.callback_query.from_user.id if is_callback else update.effective_user.id

    # Используйте self._get_user_id(update) вместо update.effective_user.id везде, где это требуется
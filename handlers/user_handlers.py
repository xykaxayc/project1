from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
import re
from typing import Dict

from .base_handler import BaseHandler
from utils.formatters import format_status_message, format_welcome_message, escape_markdown_v2
from texts import get_json, get_text

class UserHandlers(BaseHandler):
    """Обработчики пользовательских команд"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = get_json("handlers.user_messages")
        self.menu_messages = self.messages["menu"]
        self.status_messages = self.messages["status"]

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        telegram_id = update.effective_user.id
        telegram_username = update.effective_user.username
        first_name = update.effective_user.first_name
        
        if context.args and context.args[0].startswith("link_"):
            await self._handle_invitation_link(update, context.args[0], telegram_id, telegram_username)
            return
        
        user = await self.get_verified_user(telegram_id)
        
        if user:
            inline_keyboard = self.create_main_menu_keyboard(user)
            reply_keyboard = self.create_reply_keyboard(user, self.is_admin(telegram_id))
            message = format_welcome_message(first_name, user)
            
            await update.message.reply_text(message, reply_markup=reply_keyboard)
            await update.message.reply_text("Выберите действие:", reply_markup=inline_keyboard)
        else:
            await self._show_registration_options(update)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status"""
        telegram_id = update.effective_user.id
        user_state = self.get_user_state(telegram_id)
        active_account = user_state.get('active_account')
        
        accounts = self.db.get_users_by_telegram_id(telegram_id)
        if not accounts:
            message_obj = update.callback_query.message if update.callback_query else update.message
            await self._show_account_not_found(message_obj)
            return
            
        user = next((u for u in accounts if u['marzban_username'] == active_account), accounts[0])

        if not user or not user.get('marzban_username'):
            message_obj = update.callback_query.message if update.callback_query else update.message
            await self._show_account_not_found(message_obj)
            return

        message_obj = update.callback_query.message if update.callback_query else update.message
        await self._show_user_status(message_obj, user['marzban_username'], edit_message=bool(update.callback_query))

    async def my_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения своего Telegram ID"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        
        message = f"🆔 **ВАША ИНФОРМАЦИЯ:**\n\n"
        message += f"ID: `{user_id}`\n"
        message += f"Имя: {escape_markdown_v2(first_name)}\n"
        if username:
            message += f"Username: @{escape_markdown_v2(username)}\n"
        
        is_admin = self.is_admin(user_id)
        message += f"Статус: {'👑 Администратор' if is_admin else '👤 Пользователь'}\n"
        
        await update.message.reply_text(message, parse_mode='MarkdownV2')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        is_admin_user = self.is_admin(update.effective_user.id)

        if is_admin_user:
            text = get_text("admin.commands")
        else:
            text = "Этот бот поможет вам управлять вашей VPN подпиской.\n\n"
            text += "Используйте кнопки меню для проверки статуса, управления подпиской и оплаты."
        
        await update.message.reply_text(text, parse_mode='Markdown')

    async def _handle_invitation_link(self, update: Update, invite_code: str, telegram_id: int, telegram_username: str):
        """Обработка ссылки приглашения"""
        parts = invite_code.split("_")
        if not invite_code.startswith("link_") or len(parts) < 3:
            await update.message.reply_text("❌ Неверный формат кода приглашения.")
            return
        
        marzban_username = "_".join(parts[1:-1])
        
        if self.db.link_telegram_account(marzban_username, telegram_id, telegram_username):
            self.marzban.sync_telegram_id_to_marzban_notes(marzban_username, telegram_id, telegram_username)
            await update.message.reply_text(get_text("messages.ACCOUNT_LINKED"))
            await self.start_command(update, ContextTypes.DEFAULT_TYPE)
        else:
            await update.message.reply_text("❌ Ошибка связывания: код недействителен или аккаунт уже связан.")
    
    async def _show_registration_options(self, update: Update):
        """Показать опции регистрации для нового пользователя"""
        keyboard = [
            [InlineKeyboardButton("🆕 Создать новый аккаунт", callback_data="register_new")],
            [InlineKeyboardButton("🔗 У меня есть аккаунт", callback_data="link_existing")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            self.menu_messages.get("welcome_unlinked", "👋 Добро пожаловать!"), 
            reply_markup=self.create_reply_keyboard(user=None)
        )
        await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

    async def _show_user_status(self, message, marzban_username: str, edit_message: bool = False):
        """Отображение статуса пользователя"""
        stats = self.marzban.get_user_usage_stats(marzban_username)
        text, keyboard_buttons = format_status_message(stats, marzban_username, self.marzban)
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)

        if edit_message:
            await message.edit_text(text, parse_mode='HTML', reply_markup=reply_markup)
        else:
            await message.reply_text(text, parse_mode='HTML', reply_markup=reply_markup)

    async def main_menu_callback(self, query, telegram_id: int):
        """Обработка возврата в главное меню"""
        user = await self.get_verified_user(telegram_id)
        keyboard = self.create_main_menu_keyboard(user)
        
        first_name = query.from_user.first_name
        message_text = format_welcome_message(first_name, user) if user else self.menu_messages.get("welcome_unlinked")

        try:
            await query.edit_message_text(message_text, reply_markup=keyboard)
        except Exception:
            await query.message.reply_text(message_text, reply_markup=keyboard)
            
    async def support_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE = None):
        """Команда /support — информация о поддержке"""
        await update.message.reply_text(get_text("user.support.SUPPORT_INFO"))

    async def download_app_callback(self, query_or_update: Update):
        """Обработчик для кнопки 'Скачать приложение'"""
        text = get_text("user.apps.INFO_MESSAGE", default="Информация о приложениях.")
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
        
        target_message = query_or_update.message if isinstance(query_or_update, Update) else query_or_update.message
        
        if isinstance(query_or_update, Update):
            await target_message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=True)
        else:
            await target_message.edit_text(text, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=True)

    async def support_callback(self, query, context=None):
        """Обработка колбэка поддержки"""
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]])
        await query.edit_message_text(get_json("handlers.user_messages")["support_info"], reply_markup=reply_markup)

    async def _show_account_not_found(self, message: Update.message):
        msg = get_json("handlers.user_messages")["account_not_found"]
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🆘 Техподдержка", callback_data="support")],
            [InlineKeyboardButton("Создать новую подписку", callback_data="register_new")]
        ])
        if hasattr(message, 'edit_text'):
            await message.edit_text(msg, reply_markup=reply_markup)
        else:
            await message.reply_text(msg, reply_markup=reply_markup)
    
    def create_main_menu_keyboard(self, user: Dict = None) -> InlineKeyboardMarkup:
        # ... (код метода без изменений)
        pass

    async def my_accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # ... (код метода без изменений)
        pass

    async def set_active_account_callback(self, query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
        # ... (код метода без изменений)
        pass
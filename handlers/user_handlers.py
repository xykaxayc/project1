from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
        
        # Проверяем, есть ли код приглашения
        if context.args and context.args[0].startswith("link_"):
            await self._handle_invitation_link(update, context.args[0], telegram_id, telegram_username)
            return
        
        # Проверяем, связан ли пользователь
        user = await self.get_verified_user(telegram_id)
        
        if user:
            # Пользователь уже связан
            keyboard = self.create_main_menu_keyboard(user)
            message = format_welcome_message(first_name, user)
            await update.message.reply_text(message, reply_markup=keyboard)
        else:
            # Новый пользователь
            await self._show_registration_options(update)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status"""
        telegram_id = update.effective_user.id
        user_state = self.get_user_state(telegram_id)
        active_account = user_state.get('active_account')
        if active_account:
            accounts = self.db.get_users_by_telegram_id(telegram_id)
            user = next((u for u in accounts if u['marzban_username'] == active_account), None)
        else:
            user = await self.get_verified_user(telegram_id)

        if not user or not user.get('marzban_username'):
            await self._show_account_not_found(update)
            return

        await self._show_user_status(update.message, user['marzban_username'])
    
    async def my_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для получения своего Telegram ID"""
        user_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        
        message = f"🆔 **ВАША ИНФОРМАЦИЯ:**\n\n"
        message += f"ID: `{user_id}`\n"
        message += f"Имя: {first_name}\n"
        if username:
            message += f"Username: @{username}\n"
        
        is_admin = self.is_admin(user_id)
        message += f"Статус: {'👑 Администратор' if is_admin else '👤 Пользователь'}\n"
        
        if not is_admin:
            message += f"\n💡 Добавьте ваш ID ({user_id}) в конфигурацию для получения прав администратора."
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        user = await self.get_verified_user(update.effective_user.id)
        is_admin_user = self.is_admin(update.effective_user.id)

        if is_admin_user:
            text = self.menu_messages.get("admin_help", "Справка для администратора недоступна.")
        else:
            text = "Этот бот поможет вам управлять вашей VPN подпиской.\n\n"
            if user:
                text += "Вы можете проверить /status, управлять /subscription и т.д."
            else:
                text += "Используйте /start для начала работы."
        await update.message.reply_text(text, reply_markup=self.create_reply_keyboard(user, is_admin_user))
    
    async def _handle_invitation_link(self, update: Update, invite_code: str, telegram_id: int, telegram_username: str):
        """Обработка ссылки приглашения"""
        if not invite_code.startswith("link_"):
            await update.message.reply_text("❌ Неверный код приглашения.")
            return
        
        # Извлекаем имя пользователя из кода
        parts = invite_code.split("_")
        if len(parts) < 3:
            await update.message.reply_text("❌ Неверный формат кода приглашения.")
            return
        
        marzban_username = "_".join(parts[1:-1])
        
        # Связываем аккаунт в базе данных бота
        if self.db.link_telegram_account(marzban_username, telegram_id, telegram_username):
            # Синхронизируем Telegram ID в примечания Marzban
            success = self.marzban.sync_telegram_id_to_marzban_notes(
                marzban_username, telegram_id, telegram_username
            )
            
            if success:
                self.logger.info(f"Telegram ID {telegram_id} добавлен в примечания Marzban для {marzban_username}")
            else:
                self.logger.warning(f"Не удалось добавить Telegram ID в примечания Marzban для {marzban_username}")
            
            await update.message.reply_text(self.menu_messages.get("account_linked", "Аккаунт успешно привязан!"))
        else:
            await update.message.reply_text(
                "❌ Ошибка связывания аккаунта.\n"
                "Возможно, код недействителен или аккаунт уже связан."
            )
    
    async def _show_registration_options(self, update: Update):
        """Показать опции регистрации для нового пользователя"""
        if self.config.NEW_USER_SETTINGS.get("auto_create", True):
            keyboard = [
                [InlineKeyboardButton("🆕 Создать новый аккаунт", callback_data="register_new")],
                [InlineKeyboardButton("🔗 У меня есть аккаунт", callback_data="link_existing")],
                [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("🔗 Связать аккаунт", callback_data="link_existing")],
                [InlineKeyboardButton("📞 Поддержка", callback_data="support")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(self.menu_messages.get("welcome_unlinked", "👋 Добро пожаловать!"), reply_markup=reply_markup)
    
    async def _show_user_status(self, message, marzban_username: str, edit_message: bool = False):
        """Отображение статуса пользователя"""
        try:
            self.logger.info(f"Запрос статуса для пользователя {marzban_username}")

            user_info = self.marzban.get_user(marzban_username)
            if not user_info:
                error_text = self.status_messages["error"]["get_info"].format(
                    username=escape_markdown_v2(marzban_username)
                )
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                reply_markup = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu"),
                        InlineKeyboardButton("Создать подписку", callback_data="register_new")
                    ]
                ])
                if edit_message:
                    await message.edit_text(error_text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                else:
                    await message.reply_text(error_text, parse_mode='MarkdownV2', reply_markup=reply_markup)
                return

            db_user = self.db.get_user_by_marzban_username(marzban_username)
            telegram_id = db_user['telegram_id'] if db_user and db_user.get('telegram_id') else None
            telegram_username = db_user['telegram_username'] if db_user and db_user.get('telegram_username') else None

            status_raw = user_info.get('status', 'unknown')
            expire_days, expire_date_str = self.marzban.get_subscription_days_left(user_info.get('expire'))
            
            status_texts = self.status_messages["user_status"]
            if expire_days is not None and expire_days < 0:
                status = status_texts["expired"]
            else:
                status = status_texts["active"] if status_raw == 'active' else status_texts["disabled"]

            data_limit_gb = self.marzban.format_data_limit(user_info.get('data_limit'))
            used_traffic_gb = self.marzban.format_used_traffic(user_info.get('used_traffic'))
            
            try:
                formatted_used_traffic = f"{float(used_traffic_gb):.2f} GB" if used_traffic_gb else "0 GB"
            except (ValueError, TypeError):
                formatted_used_traffic = used_traffic_gb or "0 GB"

            try:
                formatted_data_limit = f"{float(data_limit_gb):.2f} GB" if data_limit_gb and data_limit_gb != status_texts["unlimited"] else status_texts["unlimited"]
            except (ValueError, TypeError):
                formatted_data_limit = data_limit_gb or status_texts["unlimited"]

            # Форматируем профиль
            profile = self.status_messages["profile"]
            telegram_status = self.status_messages["user_status"]["telegram"]

            safe_username = escape_markdown_v2(marzban_username)
            safe_status = escape_markdown_v2(status)
            safe_used_traffic = escape_markdown_v2(formatted_used_traffic)
            safe_data_limit = escape_markdown_v2(formatted_data_limit)
            safe_expire_date = escape_markdown_v2(expire_date_str if expire_date_str else "Не указано")
            safe_expire_days = escape_markdown_v2(str(expire_days) if expire_days is not None else "0")

            if telegram_id:
                safe_telegram_id = f"`{escape_markdown_v2(str(telegram_id))}`"
            else:
                safe_telegram_id = telegram_status["not_linked"]

            if telegram_username:
                safe_telegram_username = f"@{escape_markdown_v2(str(telegram_username))}"
            else:
                safe_telegram_username = telegram_status["not_specified"]

            text = (
                profile["header"] +
                profile["username"].format(username=safe_username) +
                profile["telegram_id"].format(telegram_id=safe_telegram_id) +
                profile["telegram_username"].format(telegram_username=safe_telegram_username) +
                profile["stats_header"] +
                profile["status"].format(status=safe_status) +
                profile["traffic"].format(used_traffic=safe_used_traffic, data_limit=safe_data_limit) +
                profile["expire_date"].format(expire_date=safe_expire_date) +
                profile["days_left"].format(days_left=safe_expire_days)
            )

            keyboard = [
                [InlineKeyboardButton("🔄 Обновить", callback_data="status")],
                [InlineKeyboardButton("🔗 Получить ссылку", callback_data=f"get_subscription_{marzban_username}")],
                [InlineKeyboardButton("💳 Продлить подписку", callback_data="payment")],
                [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            if edit_message:
                await message.edit_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')
            else:
                await message.reply_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')

        except Exception as e:
            self.logger.error(f"Ошибка при получении статуса пользователя {marzban_username}: {str(e)}")
            error_message = get_text("messages.errors.GENERIC_ERROR")
            if edit_message:
                await message.edit_text(error_message, parse_mode='MarkdownV2')
            else:
                await message.reply_text(error_message, parse_mode='MarkdownV2')
    
    async def main_menu_callback(self, query, telegram_id: int):
        """Обработка возврата в главное меню"""
        user = await self.get_verified_user(telegram_id)
        keyboard = self.create_main_menu_keyboard(user)
        
        first_name = query.from_user.first_name
        
        if user:
            message = format_welcome_message(first_name, user)
        else:
            message = self.menu_messages.get("welcome_unlinked", "👋 Добро пожаловать!")
        
        try:
            await query.edit_message_text(message, reply_markup=keyboard)
        except Exception as e:
            self.logger.warning(f"Не удалось отредактировать главное меню: {e}")
            await query.message.reply_text(message, reply_markup=keyboard)
    
    async def support_command(self, update, context=None):
        """Команда /support — информация о поддержке"""
        try:
            await update.message.reply_text(get_text("user.support.SUPPORT_INFO"))
        except Exception as e:
            self.logger.warning(f"Ошибка показа поддержки: {e}")
            await update.message.reply_text(get_text("messages.errors.GENERIC_ERROR"))

    async def download_app_command(self, update: Update):
        """Обработчик команды для кнопки 'Скачать приложение'"""
        query_or_message = update.callback_query or update.message
        
        text = """
📱 ПРИЛОЖЕНИЯ ДЛЯ ПОДКЛЮЧЕНИЯ

Выберите вашу операционную систему:

⬇️ **Windows**
[V2RayN](https://github.com/2dust/v2rayN/releases/latest) - Популярный клиент с множеством функций.

⬇️ **Android**
[V2RayNG](https://github.com/2dust/v2rayNG/releases/latest) - Простой и удобный клиент.

⬇️ **iOS & macOS**
[FoXray](https://apps.apple.com/us/app/foxray/id6448898396) - Поддерживает множество протоколов.
[V2Box](https://apps.apple.com/us/app/v2box-v2ray-client/id6446814690) - Еще один хороший вариант для Apple.

*Инструкция:*
1. Скачайте и установите приложение.
2. Скопируйте ссылку-подписку из бота.
3. В приложении добавьте новую подписку и вставьте ссылку.
4. Обновите подписку, чтобы получить конфигурации.
        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад в главное меню", callback_data="main_menu")]
        ])
        
        # Определяем, как отвечать
        if hasattr(query_or_message, 'edit_message_text'):
            await query_or_message.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=True)
        else:
            await query_or_message.reply_text(text, parse_mode='Markdown', reply_markup=keyboard, disable_web_page_preview=True)

    async def handle_reply_keyboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кнопок нижнего меню"""
        text = update.message.text
        telegram_id = update.effective_user.id
        buttons = self.menu_messages["buttons"]
        
        # Получаем пользователя
        user = await self.get_verified_user(telegram_id)
        is_admin_user = self.is_admin(telegram_id)
        
        # Для неавторизованных пользователей
        if not user:
            if text == buttons["create_account"]:
                from .registration_handlers import RegistrationHandlers
                reg_handler = RegistrationHandlers(self.db, self.marzban)
                return await reg_handler.start_registration_command(update, context)
            
            elif text == buttons["link_account"]:
                from .registration_handlers import RegistrationHandlers
                reg_handler = RegistrationHandlers(self.db, self.marzban)
                return await reg_handler.link_existing_command(update)

            elif text == buttons["support"]:
                return await self.support_command(update)

            elif text == buttons["help"]:
                return await self.help_command(update, context)
                
            else:
                return await self.start_command(update, context)

        # Для авторизованных пользователей
        if text == buttons["my_status"]:
            return await self.status_command(update, context)
            
        elif text == buttons["subscription_link"]:
            from .subscription_handlers import SubscriptionHandlers
            sub_handler = SubscriptionHandlers(self.db, self.marzban)
            return await sub_handler.get_user_subscription_command(update, context)
            
        elif text == buttons["payment"]:
            from .payment_handlers import PaymentHandlers
            payment_handler = PaymentHandlers(self.db, self.marzban)
            class FakeQuery:
                def __init__(self, message):
                    self.message = message
                async def answer(self): pass
                async def edit_message_text(self, *args, **kwargs):
                    return await self.message.reply_text(*args, **kwargs)
            return await payment_handler.show_payment_plans(FakeQuery(update.message))

        elif text == buttons["apps"]:
            return await self.download_app_command(update)
            
        elif text == buttons["support"]:
            return await self.support_command(update)

        elif text == buttons["main_menu"]:
            return await self.start_command(update, context)
            
        # Админские кнопки
        elif text == buttons["admin_panel"] and is_admin_user:
            from .admin_handlers import AdminHandlers
            admin_handler = AdminHandlers(self.db, self.marzban)
            return await admin_handler.admin_panel_command(update, context)

        elif text == buttons["stats"] and is_admin_user:
            from .admin_handlers import AdminHandlers
            admin_handler = AdminHandlers(self.db, self.marzban)
            return await admin_handler.stats_command(update, context)

        elif text == buttons["new_users"] and is_admin_user:
            from .admin_handlers import AdminHandlers
            admin_handler = AdminHandlers(self.db, self.marzban)
            return await admin_handler.new_users_command(update, context)

        elif text == buttons["pending_payments"] and is_admin_user:
            from .admin_handlers import AdminHandlers
            admin_handler = AdminHandlers(self.db, self.marzban)
            return await admin_handler.pending_payments_command(update, context)

        elif text == buttons["links"] and is_admin_user:
            from .admin_handlers import AdminHandlers
            admin_handler = AdminHandlers(self.db, self.marzban)
            return await admin_handler.admin_links_command(update, context)

        elif text == buttons["commands"] and is_admin_user:
            try:
                await update.message.reply_text(get_text("admin.commands"))
            except Exception as e:
                self.logger.warning(f"Ошибка показа admin_help: {e}")
                await update.message.reply_text(self.menu_messages["commands_unavailable"])

        else:
            await update.message.reply_text(
                self.menu_messages["use_buttons"],
                reply_markup=self.create_reply_keyboard(user, is_admin_user)
            )
    
    async def my_accounts_command(self, update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все аккаунты, связанные с этим Telegram ID"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        is_callback = hasattr(update, 'from_user')  # если это query
        if is_callback:
            telegram_id = update.from_user.id
            message_obj = update.message if hasattr(update, 'message') else update
        else:
            telegram_id = update.effective_user.id
            message_obj = update.message
        accounts = self.db.get_users_by_telegram_id(telegram_id)

        if not accounts:
            if is_callback and hasattr(update, 'edit_message_text'):
                await update.edit_message_text(
                    self.menu_messages["account_not_linked"],
                    reply_markup=self.create_reply_keyboard()
                )
            else:
                await message_obj.reply_text(
                    self.menu_messages["account_not_linked"],
                    reply_markup=self.create_reply_keyboard()
                )
            return

        my_accounts = self.menu_messages["my_accounts"]
        message = my_accounts["header"]
        for acc in accounts:
            message += my_accounts["account_line"].format(
                username=acc['marzban_username'],
                status=acc['subscription_status']
            )
        message += my_accounts["footer"]
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
        ])
        if is_callback and hasattr(update, 'edit_message_text'):
            await update.edit_message_text(message, reply_markup=reply_markup)
        else:
            await message_obj.reply_text(message, reply_markup=reply_markup)

    async def choose_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать пользователю список аккаунтов для выбора активного"""
        telegram_id = update.effective_user.id
        accounts = self.db.get_users_by_telegram_id(telegram_id)
        print(f"[DEBUG] choose_account_command accounts: {accounts}")  # Debug-вывод
        if not accounts:
            msg = "У вас нет ни одного аккаунта, зарегистрированного через этого бота."
            if getattr(update, 'message', None):
                await update.message.reply_text(msg)
            else:
                await update.effective_message.reply_text(msg)
            return
        keyboard = []
        for acc in accounts:
            keyboard.append([
                InlineKeyboardButton(
                    f"{acc['marzban_username']} ({acc['subscription_status']})",
                    callback_data=f"set_active_account_{acc['marzban_username']}"
                )
            ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = "Выберите аккаунт для управления:"
        if getattr(update, 'message', None):
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.effective_message.reply_text(text, reply_markup=reply_markup)

    async def set_active_account_callback(self, query, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик выбора активного аккаунта по callback_data"""
        telegram_id = query.from_user.id
        data = query.data
        if not data.startswith("set_active_account_"):
            return
        marzban_username = data.replace("set_active_account_", "")
        # Сохраняем активный аккаунт в user_state
        self.set_user_state(telegram_id, {
            'active_account': marzban_username
        })
        await query.answer()
        await query.edit_message_text(f"Аккаунт {marzban_username} выбран как активный! Теперь все действия будут выполняться для этого аккаунта.")
    
    def create_main_menu_keyboard(self, user: Dict = None) -> InlineKeyboardMarkup:
        keyboard = [
            [InlineKeyboardButton("📊 Статус подписки", callback_data="status")],
            [InlineKeyboardButton("💳 Оплатить подписку", callback_data="payment")],
            [InlineKeyboardButton("👥 Мои аккаунты", callback_data="my_accounts")],
            [InlineKeyboardButton("📞 Поддержка", callback_data="support")],
            [InlineKeyboardButton("➕ Новый аккаунт", callback_data="register_new")],
        ]
        return InlineKeyboardMarkup(keyboard)

    async def support_callback(self, query, context=None):
        """Обработка колбэка поддержки"""
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        try:
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад", callback_data="main_menu")]
            ])
            await query.edit_message_text(get_json("handlers.user_messages")["support_info"], reply_markup=reply_markup)
        except Exception as e:
            self.logger.warning(f"Ошибка показа поддержки (callback): {e}")
            await query.edit_message_text(get_text("messages.errors.GENERIC_ERROR"))

    async def _show_account_not_found(self, update):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        msg = get_json("handlers.user_messages")["account_not_found"]
        reply_markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🆘 Техподдержка", callback_data="support"),
                InlineKeyboardButton("Создать новую подписку", callback_data="register_new")
            ]
        ])
        if hasattr(update, 'edit_message_text'):
            await update.edit_message_text(msg, reply_markup=reply_markup)
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup)
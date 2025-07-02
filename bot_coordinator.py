import logging
from telegram import Update
from telegram.ext import ContextTypes
from texts import get_text, get_json

# ИСПРАВЛЕНО: Прямой импорт классов из их модулей для разрыва цикла
from handlers.user_handlers import UserHandlers
from handlers.admin_handlers import AdminHandlers
from handlers.payment_handlers import PaymentHandlers
from handlers.subscription_handlers import SubscriptionHandlers
from handlers.registration_handlers import RegistrationHandlers

from database_manager import DatabaseManager
from marzban_api import MarzbanAPI

logger = logging.getLogger(__name__)

class BotCoordinator:
    """Главный координатор всех обработчиков бота"""

    def __init__(self, db_manager: DatabaseManager, marzban_api: MarzbanAPI):
        self.db = db_manager
        self.marzban = marzban_api
        
        # Инициализация всех обработчиков остается прежней
        self.user_handlers = UserHandlers(db_manager, marzban_api)
        self.admin_handlers = AdminHandlers(db_manager, marzban_api)
        self.payment_handlers = PaymentHandlers(db_manager, marzban_api)
        self.subscription_handlers = SubscriptionHandlers(db_manager, marzban_api)
        self.registration_handlers = RegistrationHandlers(db_manager, marzban_api)

    # --- Весь остальной код этого файла остается таким же, как в предыдущем ответе ---
    # (методы start_command, status_command, handle_text_messages и т.д.)
    
    # ========== ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ ==========
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.user_handlers.start_command(update, context)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.user_handlers.status_command(update, context)
    
    async def my_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.user_handlers.my_id_command(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.user_handlers.help_command(update, context)
    
    async def my_accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.user_handlers.my_accounts_command(update, context)
    
    async def choose_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.user_handlers.choose_account_command(update, context)
    
    # ========== ПОДПИСКИ ==========
    async def subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.subscription_handlers.get_user_subscription_command(update, context)
    
    async def test_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.subscription_handlers.test_subscription_command(update, context)
    
    # ... и другие методы ...

    # ========== ОБРАБОТЧИКИ ФАЙЛОВ И СООБЩЕНИЙ ==========
    async def handle_receipt_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        return await self.payment_handlers.handle_receipt_upload(update, context)

    async def handle_text_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений (кнопки нижнего меню и ввод пользователя)"""
        if not (update.message and update.message.text):
            return

        text = update.message.text
        telegram_id = update.effective_user.id
        buttons = get_json("handlers.user_messages")["menu"]["buttons"]

        is_admin_user = self.user_handlers.is_admin(telegram_id)

        class FakeQuery:
            def __init__(self, message, user):
                self.message = message
                self.from_user = user
            async def answer(self, *args, **kwargs): pass
            async def edit_message_text(self, *args, **kwargs):
                return await self.message.reply_text(*args, **kwargs)

        if text == buttons["my_status"]:
            return await self.status_command(update, context)
        elif text == buttons["subscription_link"]:
            return await self.subscription_command(update, context)
        elif text == buttons["apps"]:
            return await self.user_handlers.download_app_callback(update)
        elif text == buttons["support"]:
            return await self.user_handlers.support_command(update, context)
        elif text == buttons["help"]:
            return await self.help_command(update, context)
        elif text == buttons["main_menu"]:
            return await self.start_command(update, context)
        elif text == buttons["payment"]:
            return await self.payment_handlers.show_payment_accounts(FakeQuery(update.message, update.effective_user))
        elif text == buttons["create_account"]:
            return await self.registration_handlers.start_registration_callback(FakeQuery(update.message, update.effective_user), context)
        elif text == buttons["link_account"]:
            return await self.registration_handlers.link_existing_callback(FakeQuery(update.message, update.effective_user))
        elif is_admin_user and text == buttons.get("admin_panel"):
            return await self.admin_handlers.admin_panel_command(update, context)
        # ... и другие кнопки
        else:
            return await self.registration_handlers.handle_text_messages(update, context)

    # ========== ОБРАБОТЧИК КОЛБЭКОВ ==========
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # ... код этого метода остается без изменений
        pass
        
    # ========== ОБРАБОТЧИК ОШИБОК ==========
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        # ... код этого метода остается без изменений
        pass
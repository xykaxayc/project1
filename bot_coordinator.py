import logging
from telegram import Update
from telegram.ext import ContextTypes
from texts import get_text

from handlers import (
    UserHandlers, 
    AdminHandlers, 
    PaymentHandlers, 
    SubscriptionHandlers, 
    RegistrationHandlers
)
from database_manager import DatabaseManager
from marzban_api import MarzbanAPI

logger = logging.getLogger(__name__)

class BotCoordinator:
    """Главный координатор всех обработчиков бота"""
    
    def __init__(self, db_manager: DatabaseManager, marzban_api: MarzbanAPI):
        self.db = db_manager
        self.marzban = marzban_api
        
        # Инициализируем все обработчики
        self.user_handlers = UserHandlers(db_manager, marzban_api)
        self.admin_handlers = AdminHandlers(db_manager, marzban_api)
        self.payment_handlers = PaymentHandlers(db_manager, marzban_api)
        self.subscription_handlers = SubscriptionHandlers(db_manager, marzban_api)
        self.registration_handlers = RegistrationHandlers(db_manager, marzban_api)
    
    # ========== ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ ==========
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        return await self.user_handlers.start_command(update, context)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status"""
        return await self.user_handlers.status_command(update, context)
    
    async def my_id_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /my_id"""
        return await self.user_handlers.my_id_command(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        return await self.user_handlers.help_command(update, context)
    
    async def my_accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /my_accounts — список всех аккаунтов пользователя"""
        return await self.user_handlers.my_accounts_command(update, context)
    
    async def choose_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда выбора аккаунта"""
        return await self.user_handlers.choose_account_command(update, context)
    
    # ========== ПОДПИСКИ ==========
    
    async def subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда получения ссылки подписки"""
        return await self.subscription_handlers.get_user_subscription_command(update, context)
    
    async def test_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда тестирования ссылок подписки"""
        return await self.subscription_handlers.test_subscription_command(update, context)
    
    async def fix_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда исправления ссылок подписки"""
        return await self.subscription_handlers.fix_subscription_urls_command(update, context)
    
    async def diagnose_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда полной диагностики подписок"""
        return await self.subscription_handlers.diagnose_subscription_command(update, context)
    
    async def quick_fix_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда быстрого исправления ссылки"""
        return await self.subscription_handlers.quick_fix_command(update, context)
    
    # ========== АДМИНИСТРАТИВНЫЕ КОМАНДЫ ==========
    
    async def admin_links_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда генерации ссылок для привязки"""
        return await self.admin_handlers.admin_links_command(update, context)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда статистики"""
        return await self.admin_handlers.stats_command(update, context)
    
    async def user_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда информации о пользователе"""
        return await self.admin_handlers.user_info_command(update, context)
    
    async def pending_payments_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда просмотра ожидающих платежей"""
        return await self.admin_handlers.pending_payments_command(update, context)
    
    async def new_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда просмотра новых пользователей"""
        return await self.admin_handlers.new_users_command(update, context)
    
    async def delete_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда удаления пользователя"""
        return await self.admin_handlers.delete_user_command(update, context)
    
    async def cleanup_accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда очистки аккаунтов"""
        return await self.admin_handlers.cleanup_accounts_command(update, context)
    
    # ========== ПЛАТЕЖИ ==========
    
    async def confirm_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда подтверждения оплаты"""
        return await self.payment_handlers.confirm_payment_command(update, context)
    
    async def approve_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда одобрения заявки на оплату"""
        return await self.payment_handlers.approve_payment_command(update, context)
    
    async def reject_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда отклонения заявки на оплату"""
        return await self.payment_handlers.reject_payment_command(update, context)
    
    # ========== ОБРАБОТЧИКИ ФАЙЛОВ И СООБЩЕНИЙ ==========
    
    async def handle_receipt_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка загрузки чеков"""
        return await self.payment_handlers.handle_receipt_upload(update, context)
    
    async def handle_text_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка текстовых сообщений"""
        # Сначала проверяем, это кнопка нижнего меню
        if update.message and update.message.text:
            # Список кнопок нижнего меню
            menu_buttons = [
                "🏠 Главное меню", "📊 Мой статус", "🔗 Ссылка подписки", 
                "💳 Оплатить", "📱 Приложения", "📞 Поддержка", "ℹ️ Помощь",
                "🆕 Создать аккаунт", "🔗 Связать аккаунт", "👑 Админ панель", 
                "📊 Статистика", "👥 Новые пользователи", "💰 Ожидающие платежи",
                "🔗 Ссылки для привязки", "🔧 Команды", "◀️ Назад"
            ]
            
            if update.message.text in menu_buttons:
                return await self.user_handlers.handle_reply_keyboard(update, context)
        
        # Если это не кнопка меню, передаем в обработчик регистрации
        return await self.registration_handlers.handle_text_messages(update, context)
    
    # ========== ОБРАБОТЧИК КОЛБЭКОВ ==========
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Главный обработчик всех колбэков"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        telegram_id = query.from_user.id
        
        try:
            # Основные навигационные колбэки
            if data == "main_menu":
                return await self.user_handlers.main_menu_callback(query, telegram_id)
            
            elif data == "support":
                return await self.user_handlers.support_callback(query)
            
            elif data == "download_app":
                return await self.user_handlers.download_app_callback(query)
            
            # Регистрация и связывание
            elif data == "register_new":
                return await self.registration_handlers.start_registration_callback(query, context)
            
            elif data == "link_existing":
                return await self.registration_handlers.link_existing_callback(query)
            
            # Статус пользователя
            elif data == "status":
                user = await self.user_handlers.get_verified_user(telegram_id)
                if not user:
                    await query.edit_message_text(get_text("messages/ACCOUNT_NOT_LINKED"))
                    return
                return await self.user_handlers._show_user_status(query.message, user['marzban_username'], edit_message=True)
            
            # Подписки
            elif data.startswith("get_subscription_"):
                username = data.replace("get_subscription_", "")
                return await self.subscription_handlers.handle_subscription_callback(query, username)
            
            elif data.startswith("test_sub_"):
                username = data.replace("test_sub_", "")
                return await self.subscription_handlers.test_subscription_callback(query, username)
            
            # Платежи
            elif data == "payment":
                return await self.payment_handlers.show_payment_accounts(query)
            
            elif data.startswith("payacc_"):
                marzban_username = data.replace("payacc_", "")
                return await self.payment_handlers.show_payment_plans_for_account(query, marzban_username)
            
            elif data.startswith("plan_"):
                # plan_{id}_{username}
                parts = data.split("_")
                if len(parts) == 3:
                    plan_id = parts[1]
                    marzban_username = parts[2]
                    return await self.payment_handlers.process_payment_plan(query, plan_id, marzban_username)
                else:
                    # старый формат (без username)
                    plan_id = data.replace("plan_", "")
                    return await self.payment_handlers.process_payment_plan(query, plan_id)
            
            elif data.startswith("paid_"):
                # paid_{plan_id}_{username} или paid_{plan_id}
                parts = data.split("_")
                if len(parts) == 3:
                    plan_id = parts[1]
                    marzban_username = parts[2]
                    accounts = self.user_handlers.db.get_users_by_telegram_id(telegram_id)
                    user = next((u for u in accounts if u['marzban_username'] == marzban_username), None)
                    if not user:
                        await query.edit_message_text(get_text("messages/USER_NOT_FOUND"))
                        return
                    return await self.payment_handlers.handle_payment_claim(query, plan_id, user, context)
                else:
                    plan_id = data.replace("paid_", "")
                    user = await self.user_handlers.get_verified_user(telegram_id)
                    if not user:
                        await query.edit_message_text(get_text("messages/USER_NOT_FOUND"))
                        return
                    return await self.payment_handlers.handle_payment_claim(query, plan_id, user, context)
            
            elif data.startswith("set_active_account_"):
                return await self.user_handlers.set_active_account_callback(query, context)
            
            elif data == "my_accounts":
                return await self.user_handlers.my_accounts_command(query, context)
            
            else:
                logger.warning(f"Неизвестный колбэк: {data}")
                await query.answer(get_text("messages/UNKNOWN_CALLBACK"))
        except Exception as e:
            logger.error(f"Ошибка обработки колбэка {data}: {e}")
            await query.answer(get_text("messages/GENERIC_ERROR"))
    
    # ========== ОБРАБОТЧИК ОШИБОК ==========
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик ошибок"""
        logger.error(f"Ошибка обработки обновления: {context.error}")
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    get_text("messages/GENERIC_ERROR_REPLY")
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение об ошибке: {e}")
        else:
            logger.warning("Update не содержит effective_message")
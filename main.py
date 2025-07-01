#!/usr/bin/env python3
"""
Главный файл для запуска Telegram бота оплаты подписки Marzban
Обновленная модульная версия
"""

import os
import sys
import logging
import asyncio
import signal
from logging.handlers import RotatingFileHandler
from typing import Optional
from dotenv import load_dotenv

# Автоматическая загрузка переменных окружения из .env
load_dotenv()

from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Импортируем наши модули
from database_manager import DatabaseManager
from marzban_api import MarzbanAPI
from bot_coordinator import BotCoordinator
from config import get_config
from plans import PLANS
from payment_methods import PAYMENT_METHODS
from messages import MESSAGES
from enums import UserStatus, PaymentMethod, UserRole
from texts import get_text

# Получаем конфигурацию
config = get_config()

# Глобальная переменная для остановки
shutdown_event = asyncio.Event()

def setup_logging():
    """Настройка логирования"""
    # Создаем директорию для логов если её нет
    os.makedirs('logs', exist_ok=True)
    
    # Настройка форматирования
    formatter = logging.Formatter(config.LOGGING['format'])
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Файловый обработчик с ротацией
    file_handler = RotatingFileHandler(
        f"logs/{config.LOGGING['file']}",
        maxBytes=config.LOGGING['max_bytes'],
        backupCount=config.LOGGING['backup_count'],
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Настройка корневого логгера
    logging.basicConfig(
        level=getattr(logging, config.LOGGING['level']),
        handlers=[console_handler, file_handler]
    )
    
    # Снижаем уровень логирования для httpx (слишком много запросов)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.INFO)

class PaymentBot:
    """Класс главного бота с модульной архитектурой"""
    config: object
    db_manager: Optional[DatabaseManager]
    marzban_api: Optional[MarzbanAPI]
    coordinator: Optional[BotCoordinator]
    application: Optional[Application]
    
    def __init__(self) -> None:
        self.config = config
        self.db_manager = None
        self.marzban_api = None
        self.coordinator = None
        self.application = None
        
    async def initialize(self):
        """Инициализация компонентов бота"""
        logger = logging.getLogger(__name__)
        
        logger.info("🚀 Инициализация бота...")
        
        # Проверяем конфигурацию
        if not self.config.validate():
            logger.error("❌ Конфигурация содержит ошибки")
            return False
        
        # Инициализируем базу данных
        try:
            self.db_manager = DatabaseManager(self.config.DATABASE_PATH)
            logger.info("✅ База данных инициализирована")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации базы данных: {e}")
            return False
        
        # Инициализируем Marzban API
        try:
            self.marzban_api = MarzbanAPI(
                self.config.MARZBAN_URL,
                self.config.MARZBAN_USERNAME, 
                self.config.MARZBAN_PASSWORD
            )
            
            # Проверяем подключение
            if not self.marzban_api.authenticate():
                logger.error("❌ Не удалось подключиться к Marzban")
                return False
                
            logger.info("✅ Подключение к Marzban установлено")
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Marzban API: {e}")
            return False
        
        # Автоматический импорт пользователей если база пуста
        await self._auto_import_users()
        
        # Инициализируем координатор обработчиков
        self.coordinator = BotCoordinator(self.db_manager, self.marzban_api)
        
        # Создаем приложение Telegram
        self.application = Application.builder().token(self.config.TELEGRAM_TOKEN).build()
        
        # Регистрируем обработчики команд
        self._register_handlers()
        
        logger.info("✅ Бот инициализирован успешно")
        return True
    
    async def _auto_import_users(self):
        """Синхронизация пользователей между Marzban и локальной базой при запуске"""
        logger = logging.getLogger(__name__)
        try:
            stats = self.db_manager.get_statistics()
            total_users = stats['total_users']
        except Exception:
            total_users = 0

        # Получаем пользователей из Marzban
        marzban_users = self.marzban_api.get_all_users() or []
        marzban_usernames = set(user.get('username') for user in marzban_users if user.get('username'))

        # Получаем пользователей из локальной базы
        conn = self.db_manager
        # Получаем всех пользователей из локальной базы
        local_usernames = set()
        try:
            import sqlite3
            db = sqlite3.connect(self.config.DATABASE_PATH)
            cursor = db.cursor()
            cursor.execute('SELECT marzban_username FROM user_telegram_mapping')
            local_usernames = set(row[0] for row in cursor.fetchall())
            db.close()
        except Exception as e:
            logger.error(f"Ошибка получения пользователей из локальной базы: {e}")

        # Добавляем новых пользователей из Marzban
        added_count = 0
        for user in marzban_users:
            username = user.get('username')
            status = user.get('status', 'active')
            if username and username not in local_usernames:
                if self.db_manager.add_user(username, status, "Автоматически синхронизирован из Marzban"):
                    added_count += 1
                    logger.debug(f"✅ Добавлен новый пользователь: {username}")

        # Удаляем пользователей, которых нет в Marzban
        removed_count = 0
        for username in local_usernames:
            if username not in marzban_usernames:
                if self.db_manager.delete_user_by_username(username):
                    removed_count += 1
                    logger.info(f"🗑️ Удалён пользователь, отсутствующий в Marzban: {username}")

        logger.info(f"🔄 Синхронизация завершена. Добавлено: {added_count}, удалено: {removed_count}")
    
    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        # Пользовательские команды
        self.application.add_handler(CommandHandler("start", self.coordinator.start_command))
        self.application.add_handler(CommandHandler("status", self.coordinator.status_command))
        self.application.add_handler(CommandHandler("my_id", self.coordinator.my_id_command))
        self.application.add_handler(CommandHandler("help", self.coordinator.help_command))
        self.application.add_handler(CommandHandler("my_accounts", self.coordinator.my_accounts_command))
        self.application.add_handler(CommandHandler("choose_account", self.coordinator.choose_account_command))
        
        # Команды работы с подписками
        self.application.add_handler(CommandHandler("subscription", self.coordinator.subscription_command))
        self.application.add_handler(CommandHandler("sub", self.coordinator.subscription_command))  # Короткий алиас
        self.application.add_handler(CommandHandler("test_subscription", self.coordinator.test_subscription_command))
        self.application.add_handler(CommandHandler("diagnose_subscription", self.coordinator.diagnose_subscription_command))
        self.application.add_handler(CommandHandler("fix_subscription", self.coordinator.fix_subscription_command))
        self.application.add_handler(CommandHandler("quick_fix", self.coordinator.quick_fix_command))
        
        # Административные команды
        self.application.add_handler(CommandHandler("admin_links", self.coordinator.admin_links_command))
        self.application.add_handler(CommandHandler("stats", self.coordinator.stats_command))
        self.application.add_handler(CommandHandler("user_info", self.coordinator.user_info_command))
        self.application.add_handler(CommandHandler("pending", self.coordinator.pending_payments_command))
        self.application.add_handler(CommandHandler("new_users", self.coordinator.new_users_command))
        self.application.add_handler(CommandHandler("delete_user", self.coordinator.delete_user_command))
        
        # Команды обработки платежей
        self.application.add_handler(CommandHandler("confirm_payment", self.coordinator.confirm_payment_command))
        self.application.add_handler(CommandHandler("approve", self.coordinator.approve_payment_command))
        self.application.add_handler(CommandHandler("reject", self.coordinator.reject_payment_command))
        
        # Обработчики загрузки файлов (фото и документы)
        self.application.add_handler(MessageHandler(filters.PHOTO, self.coordinator.handle_receipt_upload))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.coordinator.handle_receipt_upload))
        
        # Обработчик текстовых сообщений (для регистрации)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.coordinator.handle_text_messages))
        
        # Обработчик кнопок
        self.application.add_handler(CallbackQueryHandler(self.coordinator.button_callback))
        
        # Обработчик ошибок
        self.application.add_error_handler(self.coordinator.error_handler)
    
    async def run(self):
        """Запуск бота"""
        logger = logging.getLogger(__name__)
        
        if not await self.initialize():
            logger.error("❌ Не удалось инициализировать бота")
            return
        
        logger.info("🤖 Запуск бота...")
        
        # Выводим информацию о боте
        bot_info = await self.application.bot.get_me()
        logger.info(f"🤖 Бот запущен: @{bot_info.username} ({bot_info.first_name})")
        logger.info(f"👑 Администраторы: {self.config.ADMIN_IDS}")
        logger.info(f"🏠 Marzban URL: {self.config.MARZBAN_URL}")
        
        # Генерируем ссылку для добавления бота в чат
        bot_link = f"https://t.me/{bot_info.username}"
        logger.info(f"🔗 Ссылка на бота: {bot_link}")
        
        try:
            # Используем start_polling вместо run_polling для macOS
            logger.info("🔄 Запуск polling...")
            
            async with self.application:
                await self.application.start()
                await self.application.updater.start_polling(
                    allowed_updates=['message', 'callback_query'],
                    drop_pending_updates=True
                )
                
                logger.info("✅ Бот успешно запущен и ожидает сообщения...")
                
                # Ждем до получения сигнала остановки
                try:
                    await shutdown_event.wait()  # Ждем сигнал остановки
                except asyncio.CancelledError:
                    pass
                    
        except KeyboardInterrupt:
            logger.info("🛑 Получен сигнал остановки")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            import traceback
            traceback.print_exc()
        finally:
            logger.info("🔄 Остановка бота...")
            try:
                if hasattr(self.application, 'updater') and self.application.updater.running:
                    await self.application.updater.stop()
                if self.application.running:
                    await self.application.stop()
            except Exception as e:
                logger.error(f"Ошибка при остановке: {e}")
    
    async def shutdown(self):
        """Корректное завершение работы"""
        logger = logging.getLogger(__name__)
        logger.info("✅ Бот остановлен")

def print_banner():
    """Вывод баннера при запуске"""
    print(get_text("banner"))

def signal_handler(signum, frame):
    """Обработчик сигналов для корректной остановки"""
    print(get_text("messages/BOT_STOPPED", signum=signum))
    shutdown_event.set()

async def main():
    """Главная функция"""
    print_banner()
    
    # Настраиваем логирование
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Запуск Marzban Payment Bot v2.0 (модульная версия)")
    
    # Устанавливаем обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Создаем и запускаем бота
    bot = PaymentBot()
    await bot.run()

if __name__ == "__main__":
    # Для macOS и Windows - исправляем проблему с event loop
    if sys.platform.startswith('win') or sys.platform == 'darwin':
        if sys.version_info >= (3, 8):
            try:
                # Для Python 3.8+ на macOS
                import uvloop
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            except ImportError:
                # Если uvloop не установлен, используем стандартную политику
                asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    
    try:
        # Запускаем бота
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Остановка по команде пользователя")
    except Exception as e:
        print(f"\n❌ Критическая ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
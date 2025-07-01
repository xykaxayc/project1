from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .base_handler import BaseHandler
from texts import get_json

class SubscriptionHandlers(BaseHandler):
    """Обработчики для работы с подписками и ссылками"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = get_json("handlers.subscription_messages")
        print("Loaded subscription messages:", self.messages)
    
    async def get_user_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда получения ссылки подписки пользователя"""
        # Определяем, вызвано ли через callback или команду
        is_callback = hasattr(update, 'callback_query') and update.callback_query is not None
        user_id = update.callback_query.from_user.id if is_callback else update.effective_user.id
        message_obj = update.callback_query.message if is_callback else update.message
        
        if not self.is_admin(user_id):
            # Обычные пользователи могут получить только свою ссылку
            user = await self.get_verified_user(user_id)
            if not user:
                await message_obj.reply_text(self.messages["errors"]["account_not_linked"])
                return
            username = user['marzban_username']
        else:
            # Админы могут получить ссылку любого пользователя
            if not context.args:
                user = await self.get_verified_user(user_id)
                if user:
                    username = user['marzban_username']
                else:
                    await message_obj.reply_text(
                        self.messages["errors"]["admin_usage"],
                        parse_mode='Markdown'
                    )
                    return
            else:
                username = context.args[0]
        
        await self._send_subscription_info(message_obj, username, user_id)
    
    async def handle_subscription_callback(self, query, username: str):
        """Обработка запроса ссылки подписки через колбэк"""
        await query.answer(self.messages["subscription"]["loading"])
        
        connection_info = self.marzban.get_user_connection_info(username)
        
        if not connection_info or not connection_info.get('subscription_url'):
            await query.edit_message_text(
                self.messages["errors"]["link_not_found"].format(username=username)
            )
            return
        
        subscription_url = connection_info['subscription_url']
        
        # Проверяем работоспособность ссылки
        url_status = await self._test_subscription_url(subscription_url)
        
        link_message = self.messages["subscription"]["link_message"]
        message = (
            link_message["header"] +
            link_message["user"].format(username=username) +
            link_message["status"].format(url_status=url_status) +
            link_message["main_link"].format(subscription_url=subscription_url)
        )
        
        # Добавляем дополнительные форматы если доступны
        if connection_info.get('clash_url'):
            message += link_message["clash_link"].format(clash_url=connection_info['clash_url'])
        
        message += link_message["instructions"]
        
        keyboard = [
            [InlineKeyboardButton("🔄 Обновить ссылку", callback_data=f"get_subscription_{username}")],
            [InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")]
        ]
        
        if self.is_admin(query.from_user.id):
            keyboard.insert(0, [InlineKeyboardButton("🔍 Тестировать", callback_data=f"test_sub_{username}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def test_subscription_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда тестирования ссылок подписки (для админов)"""
        if not await self.require_admin(update):
            return
        
        if not context.args:
            await update.message.reply_text(
                self.messages["errors"]["test_usage"],
                parse_mode='Markdown'
            )
            return
        
        username = context.args[0]
        
        await update.message.reply_text(
            self.messages["subscription"]["testing"].format(username=username)
        )
        
        # Тестируем различные форматы ссылок
        test_results = self.marzban.test_subscription_url(username)
        
        # Форматируем результаты
        result_messages = self.messages["subscription"]["test_results"]
        message = result_messages["header"]
        
        working_count = 0
        total_count = len(test_results)
        
        for format_name, result in test_results.items():
            if result.get('works', False):
                status = result_messages["success"]
                working_count += 1
            else:
                error = result.get('error', 'Неизвестная ошибка')
                status = result_messages["error"].format(error=error)
            
            message += result_messages["format"].format(
                format=format_name,
                status=status
            )
        
        message += result_messages["summary"].format(
            working=working_count,
            total=total_count
        )
        
        await update.message.reply_text(message)

    async def _send_subscription_info(self, message, username: str, user_id: int):
        """Отправка информации о подписке"""
        await message.reply_text(f"🔄 Получение ссылки подписки для {username}...")
        
        # Получаем информацию о подключении
        connection_info = self.marzban.get_user_connection_info(username)
        
        if not connection_info:
            await message.reply_text(f"❌ Не удалось получить информацию о пользователе {username}")
            return
        
        subscription_url = connection_info.get('subscription_url')
        
        if not subscription_url:
            await message.reply_text(f"❌ Не удалось сформировать ссылку подписки для {username}")
            return
        
        url_status = await self._test_subscription_url(subscription_url)
        
        message_text = f"🔗 **ССЫЛКА ПОДПИСКИ**\n\n"
        message_text += f"👤 Пользователь: `{username}`\n"
        message_text += f"📊 Статус: {connection_info.get('status', 'unknown')}\n"
        message_text += f"🔧 Протоколы: {', '.join(connection_info.get('protocols', []))}\n"
        message_text += f"📊 Статус ссылки: {url_status}\n\n"
        
        message_text += f"📋 **Основная ссылка:**\n"
        message_text += f"`{subscription_url}`\n\n"
        
        # Добавляем дополнительные форматы если доступны
        if connection_info.get('clash_url'):
            message_text += f"⚡ **Clash:**\n`{connection_info['clash_url']}`\n\n"
        
        if connection_info.get('v2ray_url'):
            message_text += f"🚀 **V2Ray:**\n`{connection_info['v2ray_url']}`\n\n"
        
        message_text += f"📱 **Инструкция:**\n"
        message_text += f"1. Скопируйте ссылку\n"
        message_text += f"2. Откройте VPN приложение\n"
        message_text += f"3. Добавьте подписку по ссылке\n"
        message_text += f"4. Обновите серверы и подключайтесь!"
        
        # Создаем клавиатуру с быстрыми действиями
        keyboard = []
        if self.is_admin(user_id):
            keyboard.append([InlineKeyboardButton("🔍 Тестировать ссылку", callback_data=f"test_sub_{username}")])
        
        keyboard.append([InlineKeyboardButton("◀️ Главное меню", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.reply_text(message_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def _test_subscription_url(self, url: str) -> str:
        """Быстрое тестирование ссылки подписки"""
        try:
            import requests
            response = requests.head(url, timeout=5)
            return "✅ Проверена" if response.status_code == 200 else "⚠️ Требует проверки"
        except:
            return "⚠️ Требует проверки"
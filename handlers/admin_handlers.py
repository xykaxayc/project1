import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from .base_handler import BaseHandler
from utils.formatters import format_user_info_message, format_statistics_message, format_pending_payments_message
from texts import get_text

class AdminHandlers(BaseHandler):
    """Обработчики административных команд"""
    
    def _get_user_id(self, update):
        is_callback = hasattr(update, 'callback_query') and update.callback_query is not None
        return update.callback_query.from_user.id if is_callback else update.effective_user.id

    async def admin_links_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда для генерации ссылок (только для админов)"""
        if not await self.require_admin(update):
            return
        
        unlinked_users = self.db.get_unlinked_users()
        
        if not unlinked_users:
            await update.message.reply_text(get_text("admin.ALL_USERS_LINKED"))
            return
        
        bot_username = context.bot.username
        
        await update.message.reply_text(get_text("admin.LINKS_HEADER"))
        
        for username in unlinked_users:
            invite_code = f"link_{username}_{hash(username) % 10000:04d}"
            link = f"https://t.me/{bot_username}?start={invite_code}"
            
            message = get_text("admin.LINK_USER", username=username, link=link)
            
            try:
                await update.message.reply_text(message)
            except Exception as e:
                self.logger.error(get_text("admin.LINK_SEND_ERROR", username=username, error=e))
        
        await update.message.reply_text(
            get_text("admin.LINKS_SUMMARY", count=len(unlinked_users))
        )
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда статистики (для админов)"""
        if not await self.require_admin(update):
            return
        
        stats = self.db.get_statistics()
        message = format_statistics_message(stats)
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def user_info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда получения информации о пользователе (для админов)"""
        if not await self.require_admin(update):
            return
        
        if not context.args:
            await update.message.reply_text(get_text("admin.USER_INFO_USAGE"), parse_mode='Markdown')
            return
        
        username = context.args[0]
        
        # Получаем информацию из базы данных
        db_user = self.db.get_user_by_marzban_username(username)
        if not db_user:
            await update.message.reply_text(get_text("admin.USER_NOT_FOUND", username=username))
            return
        
        # Получаем информацию из Marzban
        stats = self.marzban.get_user_usage_stats(username)
        
        message = format_user_info_message(db_user, stats, self.marzban)
        
        # История платежей
        payments = self.db.get_payment_history(marzban_username=username, limit=5)
        
        def esc(text):
            if not text:
                return '-'
            return str(text).replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`').replace('(', '\\(').replace(')', '\\)').replace('~', '\\~').replace('>', '\\>').replace('#', '\\#').replace('+', '\\+').replace('-', '\\-').replace('=', '\\=').replace('|', '\\|').replace('{', '\\{').replace('}', '\\}').replace('.', '\\.').replace('!', '\\!')
        
        if payments:
            message += f"\n{get_text('admin.LAST_PAYMENTS_HEADER')}\n"
            for payment in payments:
                dt = datetime.fromisoformat(payment['payment_date'])
                date = esc(dt.strftime('%d.%m.%Y'))
                time = esc(dt.strftime('%H:%M'))
                amount = esc(payment['amount'])
                status = esc(payment['status'])
                message += f"• {date} {time}: {amount} руб. \\({status}\\)\n"

        await update.message.reply_text(message, parse_mode='MarkdownV2')
    
    async def pending_payments_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда просмотра ожидающих заявок"""
        if not await self.require_admin(update):
            return
        
        requests = self.db.get_pending_payment_requests()
        
        if not requests:
            await update.message.reply_text("✅ Нет ожидающих заявок на оплату.")
            return
        
        message = format_pending_payments_message(requests)
        await update.message.reply_text(message)
    
    async def new_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда просмотра новых зарегистрированных пользователей"""
        if not await self.require_admin(update):
            return
        
        # Получаем пользователей зарегистрированных за последние 24 часа
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT marzban_username, telegram_id, telegram_username, registration_date, notes
            FROM user_telegram_mapping 
            WHERE registration_date >= datetime('now', '-1 day')
            AND notes LIKE '%Зарегистрирован через бота%'
            ORDER BY registration_date DESC
        ''')
        
        new_users = cursor.fetchall()
        conn.close()
        
        if not new_users:
            await update.message.reply_text("📊 За последние 24 часа новых регистраций не было.")
            return
        
        message = f"🆕 НОВЫЕ РЕГИСТРАЦИИ (24ч): {len(new_users)}\n\n"
        
        for user in new_users:
            username, telegram_id, telegram_username, reg_date, notes = user
            reg_time = datetime.fromisoformat(reg_date).strftime('%d.%m %H:%M')
            
            message += f"👤 {username}\n"
            message += f"📱 @{telegram_username or 'N/A'} (ID: {telegram_id})\n"
            message += f"🕐 {reg_time}\n"
            message += f"/user_info {username}\n\n"
        
        # Разбиваем на части если сообщение слишком длинное
        if len(message) > 4000:
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(message)
    
    async def add_telegram_note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда добавления Telegram ID в примечания пользователя (для админов)"""
        if not await self.require_admin(update):
            return
        
        if len(context.args) != 2:
            await update.message.reply_text(
                "Использование: `/add_note username telegram_id`\n\n"
                "Пример: `/add_note Dasha 123456789`",
                parse_mode='Markdown'
            )
            return
        
        username = context.args[0]
        try:
            telegram_id = int(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Telegram ID должен быть числом.")
            return
        
        # Проверяем, существует ли пользователь
        user = self.db.get_user_by_marzban_username(username)
        if not user:
            await update.message.reply_text(f"❌ Пользователь {username} не найден в базе данных.")
            return
        
        # Обновляем примечания
        success = self.db.add_telegram_id_to_notes(username, telegram_id)
        
        if success:
            await update.message.reply_text(
                f"✅ Telegram ID {telegram_id} добавлен в примечания пользователя {username}"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка добавления Telegram ID в примечания для {username}"
            )
    
    async def sync_telegram_notes_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Синхронизация примечаний с Telegram ID для всех связанных пользователей"""
        if not await self.require_admin(update):
            return
        
        await update.message.reply_text("🔄 Начинаю синхронизацию примечаний...")
        
        # Получаем всех пользователей с Telegram ID
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT marzban_username, telegram_id, telegram_username, notes
            FROM user_telegram_mapping 
            WHERE telegram_id IS NOT NULL
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        updated_count = 0
        for user_data in users:
            username, telegram_id, telegram_username, current_notes = user_data
            
            # Проверяем, есть ли уже Telegram ID в примечаниях
            if current_notes and f"Telegram ID: {telegram_id}" in current_notes:
                continue
            
            # Формируем новые примечания
            note_parts = [f"Telegram ID: {telegram_id}"]
            if telegram_username:
                note_parts.append(f"@{telegram_username}")
            
            if current_notes:
                new_notes = f"{current_notes} | {' | '.join(note_parts)}"
            else:
                new_notes = " | ".join(note_parts)
            
            # Обновляем примечания
            if self.db.update_user_notes(username, new_notes):
                updated_count += 1
        
        await update.message.reply_text(
            f"✅ Синхронизация завершена!\n"
            f"Обновлено примечаний: {updated_count}\n"
            f"Всего пользователей с Telegram: {len(users)}"
        )
    
    async def sync_to_marzban_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Синхронизация всех Telegram ID в примечания Marzban"""
        if not await self.require_admin(update):
            return
        
        await update.message.reply_text("🔄 Синхронизация Telegram ID в Marzban...")
        
        # Получаем всех связанных пользователей
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT marzban_username, telegram_id, telegram_username
            FROM user_telegram_mapping 
            WHERE telegram_id IS NOT NULL AND is_verified = TRUE
        ''')
        
        users = cursor.fetchall()
        conn.close()
        
        success_count = 0
        error_count = 0
        
        for marzban_username, telegram_id, telegram_username in users:
            success = self.marzban.sync_telegram_id_to_marzban_notes(
                marzban_username, telegram_id, telegram_username
            )
            
            if success:
                success_count += 1
                self.logger.info(f"✅ Синхронизирован {marzban_username} -> Telegram ID {telegram_id}")
            else:
                error_count += 1
                self.logger.error(f"❌ Ошибка синхронизации {marzban_username}")
        
        await update.message.reply_text(
            f"✅ Синхронизация с Marzban завершена!\n\n"
            f"✅ Успешно: {success_count}\n"
            f"❌ Ошибки: {error_count}\n"
            f"📊 Всего: {len(users)}\n\n"
            f"Теперь в панели Marzban в поле 'Примечание' будут Telegram ID пользователей."
        )
    
    async def test_marzban_note_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестирование добавления примечания в Marzban для одного пользователя"""
        if not await self.require_admin(update):
            return
        
        if len(context.args) != 1:
            await update.message.reply_text(
                "Использование: `/test_note username`\n\n"
                "Пример: `/test_note Andrey_Ios`",
                parse_mode='Markdown'
            )
            return
        
        username = context.args[0]
        
        # Получаем данные пользователя из БД
        user = self.db.get_user_by_marzban_username(username)
        if not user or not user['telegram_id']:
            await update.message.reply_text(f"❌ Пользователь {username} не найден или не связан с Telegram")
            return
        
        await update.message.reply_text(f"🔄 Тестируем добавление примечания для {username}...")
        
        # Добавляем примечание
        success = self.marzban.sync_telegram_id_to_marzban_notes(
            username, user['telegram_id'], user['telegram_username']
        )
        
        if success:
            await update.message.reply_text(
                f"✅ Примечание успешно добавлено для {username}\n"
                f"Telegram ID: {user['telegram_id']}\n"
                f"Проверьте в админ панели Marzban!"
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка добавления примечания для {username}\n"
                "Проверьте логи для детальной информации."
            )

    async def admin_panel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отображение админ панели"""
        if not await self.require_admin(update):
            return
            
        text = "👑 Админ-панель"
        keyboard = self.create_admin_keyboard()
        
        await update.message.reply_text(text, reply_markup=keyboard)
    
    async def delete_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удалить пользователя по username (только для администратора)"""
        if not self.config.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return
        if not context.args or len(context.args) < 1:
            await update.message.reply_text("Укажите username для удаления: /delete_user <username>")
            return
        username = context.args[0]
        deleted = self.db.delete_user_by_username(username)
        if deleted:
            await update.message.reply_text(f"✅ Пользователь {username} удалён из базы данных.")
        else:
            await update.message.reply_text(f"❌ Пользователь {username} не найден.")
    
    async def cleanup_accounts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет из базы пользователей, которых нет на сервере Marzban"""
        if not self.config.is_admin(update.effective_user.id):
            await update.message.reply_text("❌ Нет прав администратора.")
            return
        users = self.db.get_all_users()
        removed = []
        for user in users:
            username = user.get('marzban_username')
            if not username:
                continue
            try:
                marzban_user = self.marzban.get_user(username)
                if not marzban_user:
                    self.db.delete_user_by_username(username)
                    removed.append(username)
            except Exception as e:
                if '404' in str(e):
                    self.db.delete_user_by_username(username)
                    removed.append(username)
        if removed:
            await update.message.reply_text(f"Удалены несуществующие аккаунты: {', '.join(removed)}")
        else:
            await update.message.reply_text("Все аккаунты в базе существуют на сервере Marzban.")

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from .base_handler import BaseHandler
from plans import PLANS, Plan
from payment_methods import PAYMENT_METHODS, PaymentMethodData
from texts import get_json

class PaymentHandlers(BaseHandler):
    """Обработчики платежей и чеков"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.messages = get_json("handlers.payment_messages")
    
    async def show_payment_accounts(self, query):
        """Показать список аккаунтов для оплаты"""
        user_id = query.from_user.id
        accounts = self.db.get_users_by_telegram_id(user_id)
        if not accounts:
            await query.edit_message_text(self.messages["accounts"]["no_accounts"])
            return
            
        keyboard = []
        for acc in accounts:
            text = f"{acc['marzban_username']} ({acc['subscription_status']})"
            keyboard.append([
                InlineKeyboardButton(text, callback_data=f"payacc_{acc['marzban_username']}")
            ])
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            self.messages["accounts"]["select_account"],
            reply_markup=reply_markup
        )

    async def show_payment_plans_for_account(self, query, marzban_username: str):
        """Показать тарифы для выбранного аккаунта"""
        message = self.messages["plans"]["for_account"].format(username=marzban_username)
        keyboard = []
        
        for plan in PLANS:
            price_per_month = plan.price / (plan.duration_days / 30)
            plan_format = self.messages["plans"]["format"]
            
            if plan.description:
                plan_text = plan_format["with_description"].format(
                    name=plan.name,
                    price=plan.price,
                    description=plan.description
                )
            elif plan.duration_days > 30:
                plan_text = plan_format["with_monthly"].format(
                    name=plan.name,
                    price=plan.price,
                    price_per_month=price_per_month
                )
            else:
                plan_text = plan_format["base"].format(
                    name=plan.name,
                    price=plan.price
                )
                
            keyboard.append([
                InlineKeyboardButton(plan_text, callback_data=f"plan_{plan.id}_{marzban_username}")
            ])
            
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="payment")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    async def show_payment_plans(self, query):
        """Показать планы подписки"""
        message = self.messages["plans"]["header"]
        keyboard = []
        
        for plan in PLANS:
            price_per_month = plan.price / (plan.duration_days / 30)
            plan_format = self.messages["plans"]["format"]
            
            if plan.description:
                plan_text = plan_format["with_description"].format(
                    name=plan.name,
                    price=plan.price,
                    description=plan.description
                )
            elif plan.duration_days > 30:
                plan_text = plan_format["with_monthly"].format(
                    name=plan.name,
                    price=plan.price,
                    price_per_month=price_per_month
                )
            else:
                plan_text = plan_format["base"].format(
                    name=plan.name,
                    price=plan.price
                )
                
            keyboard.append([InlineKeyboardButton(plan_text, callback_data=f"plan_{plan.id}")])
            
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)

    async def process_payment_plan(self, query, plan_id: str, marzban_username: str = None):
        plan = next((p for p in PLANS if str(p.id) == str(plan_id)), None)
        if not plan:
            await query.edit_message_text(self.messages["payment"]["errors"]["invalid_plan"])
            self.logger.error(f"План {plan_id} не найден. Доступные планы: {[p.id for p in PLANS]}")
            return

        user_id = query.from_user.id
        if marzban_username:
            accounts = self.db.get_users_by_telegram_id(user_id)
            user = next((u for u in accounts if u['marzban_username'] == marzban_username), None)
        else:
            user_state = self.get_user_state(user_id)
            active_account = user_state.get('active_account')
            if active_account:
                accounts = self.db.get_users_by_telegram_id(user_id)
                user = next((u for u in accounts if u['marzban_username'] == active_account), None)
            else:
                user = await self.get_verified_user(user_id)

        if not user:
            await query.edit_message_text(self.messages["payment"]["errors"]["user_not_found"])
            return

        payment_details = self.messages["payment"]["details"]
        method_formats = payment_details["methods"]
        
        methods_text = []
        for method in PAYMENT_METHODS:
            if method.id == "card":
                methods_text.append(method_formats["card"].format(details=method.details))
            elif method.id == "qiwi":
                methods_text.append(method_formats["qiwi"].format(details=method.details))

        message = (
            payment_details["header"] +
            payment_details["plan_info"].format(
                plan_name=plan.name,
                plan_price=plan.price,
                plan_duration=plan.duration_days,
                plan_description=plan.description or ""
            ) +
            payment_details["user_info"].format(username=user['marzban_username']) +
            "\n".join(methods_text)
        )

        keyboard = [
            [InlineKeyboardButton(f"✅ Я оплатил {plan.price} руб.", callback_data=f"paid_{plan.id}_{user['marzban_username']}")],
            [InlineKeyboardButton("◀️ Выбрать другой план", callback_data=f"payacc_{user['marzban_username']}")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    async def handle_payment_claim(self, query, plan_id: str, user: dict, context: ContextTypes.DEFAULT_TYPE):
        """Обработка заявки об оплате"""
        plan = next((p for p in PLANS if str(p.id) == str(plan_id)), None)
        if not plan:
            self.logger.error(f"План {plan_id} не найден. Доступные планы: {[p.id for p in PLANS]}")
            await query.edit_message_text("❌ Неверный план подписки.")
            return
        
        # Создаем заявку на оплату в базе данных
        request_id = self.db.create_payment_request(
            telegram_id=user['telegram_id'],
            marzban_username=user['marzban_username'],
            plan_id=str(plan.id),  # Преобразуем в строку для совместимости
            amount=plan.price
        )
        
        if not request_id:
            await query.edit_message_text("❌ Ошибка создания заявки на оплату.")
            return
        
        # Сохраняем ID заявки в состоянии пользователя
        self.set_user_state(query.from_user.id, {
            'state': 'waiting_receipt',
            'request_id': request_id,
            'plan_id': str(plan.id),  # Преобразуем в строку для совместимости
            'username': user['marzban_username']
        })
        
        # Уведомляем пользователя
        payment_messages = get_json("handlers.payment_messages")
        payment_claim_message = await query.edit_message_text(
            payment_messages["notifications"]["payment_claim_created"].format(
                request_id=request_id,
                plan_name=plan.name,
                plan_price=plan.price,
                username=user['marzban_username']
            ),
            parse_mode='Markdown'
        )
        # Сохраняем message_id в user_state
        self.set_user_state(query.from_user.id, {
            'state': 'waiting_receipt',
            'request_id': request_id,
            'plan_id': str(plan.id),
            'username': user['marzban_username'],
            'payment_message_id': payment_claim_message.message_id
        })
        
        # Уведомляем администраторов о новой заявке
        admin_message = f"💰 **НОВАЯ ЗАЯВКА НА ОПЛАТУ #{request_id}**\n\n"
        admin_message += f"👤 Пользователь: `{user['marzban_username']}`\n"
        admin_message += f"📱 Telegram: @{query.from_user.username or 'N/A'} (ID: {query.from_user.id})\n"
        admin_message += f"📋 План: {plan.name}\n"
        admin_message += f"💰 Сумма: {plan.price} руб.\n"
        admin_message += f"📅 Период: {plan.duration_days} дней\n\n"
        admin_message += f"🕐 Ожидает загрузки чека..."
        
        await self.send_admin_notification(context, admin_message)
    
    async def handle_receipt_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка загруженных чеков (фото/документы)"""
        is_callback = hasattr(update, 'callback_query') and update.callback_query is not None
        user_id = update.callback_query.from_user.id if is_callback else update.effective_user.id
        
        # Проверяем, ожидает ли пользователь загрузку чека
        state = self.get_user_state(user_id)
        if not state or state.get('state') != 'waiting_receipt':
            return  # Игнорируем, если пользователь не в процессе оплаты
        
        request_id = state['request_id']
        plan_id = state['plan_id']
        
        # Определяем тип файла и получаем file_id
        file_id = None
        file_type = None
        file_name = "чек"
        
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            file_type = "photo"
            file_name = "фото чека"
        elif update.message.document:
            file_id = update.message.document.file_id
            file_type = "document"
            file_name = update.message.document.file_name or "документ"
        
        if not file_id:
            await update.message.reply_text(
                "❌ Неподдерживаемый тип файла.\n"
                "Пожалуйста, отправьте фото или документ (PDF, изображение)."
            )
            return
        
        # Сохраняем чек в базу данных
        success = self.db.add_receipt_to_request(request_id, file_id, file_type)
        
        if not success:
            await update.message.reply_text("❌ Ошибка сохранения чека. Попробуйте еще раз.")
            return
        
        # Удаляем сообщение с заявкой, если оно есть
        payment_message_id = state.get('payment_message_id')
        if payment_message_id:
            try:
                await context.bot.delete_message(chat_id=update.effective_user.id, message_id=payment_message_id)
            except Exception as e:
                self.logger.warning(f"Не удалось удалить сообщение с заявкой: {e}")
        # Удаляем сообщение с фото/документом
        try:
            await context.bot.delete_message(chat_id=update.effective_user.id, message_id=update.message.message_id)
        except Exception as e:
            self.logger.warning(f"Не удалось удалить сообщение с чеком: {e}")
        
        # Очищаем состояние пользователя
        self.clear_user_state(user_id)
        
        # Получаем информацию о плане
        plan = next((p for p in PLANS if str(p.id) == str(plan_id)), None)
        plan_name = plan.name if plan else f"План #{plan_id}"
        plan_price = plan.price if plan else "N/A"
        plan_duration = plan.duration_days if plan else "N/A"
        
        # Уведомляем пользователя с кнопкой 'Главное меню'
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        payment_messages = get_json("handlers.payment_messages")
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=payment_messages["notifications"]["receipt_received"].format(
                file_name=file_name,
                request_id=request_id,
                plan_name=plan_name,
                plan_price=plan_price
            ),
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # Уведомляем всех админов с чеком
        admin_message = f"📸 **ЧЕК ПОЛУЧЕН!**\n\n"
        admin_message += f"🆔 Заявка #{request_id}\n"
        admin_message += f"👤 Пользователь: `{state['username']}`\n"
        admin_message += f"📋 План: {plan_name}\n"
        admin_message += f"💰 Сумма: {plan_price} руб.\n"
        admin_message += f"📅 Период: {plan_duration} дней\n"
        admin_message += f"📱 От: @{update.effective_user.username or 'N/A'}\n\n"
        admin_message += f"**Команды для обработки:**\n"
        admin_message += f"`/approve {request_id}` - одобрить\n"
        admin_message += f"`/reject {request_id} [причина]` - отклонить"
        
        # Отправляем уведомление и чек всем админам
        for admin_id in self.config.ADMIN_IDS:
            try:
                # Отправляем сообщение
                await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode='Markdown')
                
                # Пересылаем чек
                if file_type == "photo":
                    await context.bot.send_photo(
                        chat_id=admin_id,
                        photo=file_id,
                        caption=f"Чек к заявке #{request_id}"
                    )
                elif file_type == "document":
                    await context.bot.send_document(
                        chat_id=admin_id,
                        document=file_id,
                        caption=f"Чек к заявке #{request_id}"
                    )
                
                self.logger.info(f"Чек по заявке #{request_id} отправлен админу {admin_id}")
                
            except Exception as e:
                self.logger.error(f"Ошибка отправки чека админу {admin_id}: {e}")
    
    async def confirm_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда подтверждения оплаты (для админов)"""
        if not await self.require_admin(update):
            return
        
        if len(context.args) != 2:
            await update.message.reply_text(
                "Использование: `/confirm_payment username plan_id`\n\n"
                "Пример: `/confirm_payment user123 1`\n\n"
                f"Доступные планы: {', '.join(str(p.id) for p in PLANS)}",
                parse_mode='Markdown'
            )
            return
        
        username = context.args[0]
        plan_id = context.args[1]
        
        plan = next((p for p in PLANS if str(p.id) == str(plan_id)), None)
        if not plan:
            await update.message.reply_text(
                f"❌ Неверный план подписки: {plan_id}\n\n"
                f"Доступные планы: {', '.join(str(p.id) for p in PLANS)}"
            )
            return
        
        # Продлеваем подписку в Marzban
        if self.marzban.extend_user_subscription(username, plan.duration_days):
            # Получаем пользователя для записи платежа
            user = self.db.get_user_by_marzban_username(username)
            
            if user:
                # Записываем платеж в базу
                self.db.record_payment(
                    telegram_id=user['telegram_id'] or 0,
                    marzban_username=username,
                    amount=plan.price,
                    payment_method=str(plan.id)
                )
                
                # Уведомляем пользователя
                if user['telegram_id']:
                    try:
                        message = f"✅ **ОПЛАТА ПОДТВЕРДЖЕНА!**\n\n"
                        message += f"📋 План: {plan.name}\n"
                        message += f"💰 Сумма: {plan.price} руб.\n"
                        message += f"📅 Подписка продлена на {plan.duration_days} дней\n\n"
                        message += f"🎉 Спасибо за оплату!\n"
                        message += f"Ваш VPN активен и готов к использованию."
                        
                        await context.bot.send_message(
                            chat_id=user['telegram_id'],
                            text=message,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        self.logger.error(f"Ошибка отправки уведомления пользователю {request['marzban_username']}: {e}")
            
            await update.message.reply_text(
                f"✅ **Подписка продлена успешно!**\n\n"
                f"👤 Пользователь: `{username}`\n"
                f"📋 План: {plan.name}\n"
                f"📅 Продлено на: {plan.duration_days} дней\n"
                f"💰 Сумма: {plan.price} руб.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(f"❌ Ошибка продления подписки для {username}")

    async def approve_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда одобрения платежа админом"""
        if not await self.require_admin(update):
            return
        
        if not context.args:
            await update.message.reply_text(
                "Использование: `/approve request_id [комментарий]`\n\n"
                "Пример: `/approve 123 Платеж подтвержден`",
                parse_mode='Markdown'
            )
            return
        
        try:
            request_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Неверный ID заявки.")
            return
        
        comment = " ".join(context.args[1:]) if len(context.args) > 1 else "Одобрено администратором"
        
        # Получаем заявку
        request = self.db.get_payment_request(request_id)
        if not request:
            await update.message.reply_text(f"❌ Заявка #{request_id} не найдена.")
            return
        
        if request['status'] != 'pending':
            await update.message.reply_text(f"❌ Заявка #{request_id} уже обработана (статус: {request['status']}).")
            return
        
        # Одобряем заявку
        success = self.db.approve_payment_request(request_id, update.effective_user.id, comment)
        if not success:
            await update.message.reply_text(f"❌ Ошибка одобрения заявки #{request_id}.")
            return
        
        # Получаем план и продлеваем подписку в Marzban
        plan = next((p for p in PLANS if str(p.id) == str(request['plan_id'])), None)
        if plan and self.marzban.extend_user_subscription(request['marzban_username'], plan.duration_days):
            # Записываем платеж в историю
            self.db.record_payment(
                telegram_id=request['telegram_id'],
                marzban_username=request['marzban_username'],
                amount=request['amount'],
                payment_method=str(plan.id),
                status='completed'
            )
            
            # Уведомляем пользователя
            try:
                user_message = f"✅ **ОПЛАТА ПОДТВЕРДЖЕНА!**\n\n"
                user_message += f"🆔 Заявка #{request_id}\n"
                user_message += f"📋 План: {plan.name}\n"
                user_message += f"💰 Сумма: {plan.price} руб.\n"
                user_message += f"📅 Подписка продлена на {plan.duration_days} дней\n\n"
                if comment != "Одобрено администратором":
                    user_message += f"💬 Комментарий: {comment}\n\n"
                user_message += f"🎉 Спасибо за оплату!"
                
                await context.bot.send_message(
                    chat_id=request['telegram_id'],
                    text=user_message,
                    parse_mode='Markdown',
                    reply_markup=self._main_menu_markup()
                )
            except Exception as e:
                self.logger.error(f"Ошибка отправки уведомления пользователю {request['marzban_username']}: {e}")
            
            await update.message.reply_text(
                f"✅ **Заявка #{request_id} одобрена!**\n\n"
                f"👤 Пользователь: `{request['marzban_username']}`\n"
                f"📋 План: {plan.name}\n"
                f"📅 Подписка продлена на {plan.duration_days} дней\n"
                f"💰 Сумма: {plan.price} руб.",
                parse_mode='Markdown',
                reply_markup=self._main_menu_markup()
            )
        else:
            await update.message.reply_text(
                f"❌ Ошибка продления подписки для {request['marzban_username']}\n"
                f"Заявка #{request_id} помечена как одобренная, но подписка не продлена."
            )

    async def reject_payment_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда отклонения платежа админом"""
        if not await self.require_admin(update):
            return
        
        if len(context.args) < 2:
            await update.message.reply_text(
                "Использование: `/reject request_id причина`\n\n"
                "Пример: `/reject 123 Неверная сумма на чеке`",
                parse_mode='Markdown'
            )
            return
        
        try:
            request_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Неверный ID заявки.")
            return
        
        reason = " ".join(context.args[1:])
        
        # Получаем заявку
        request = self.db.get_payment_request(request_id)
        if not request:
            await update.message.reply_text(f"❌ Заявка #{request_id} не найдена.")
            return
        
        if request['status'] != 'pending':
            await update.message.reply_text(f"❌ Заявка #{request_id} уже обработана.")
            return
        
        # Отклоняем заявку
        success = self.db.reject_payment_request(request_id, update.effective_user.id, reason)
        if not success:
            await update.message.reply_text(f"❌ Ошибка отклонения заявки #{request_id}.")
            return
        
        # Получаем план для отображения в сообщении
        plan = next((p for p in PLANS if str(p.id) == str(request['plan_id'])), None)
        plan_name = plan.name if plan else f"План #{request['plan_id']}"
        
        # Уведомляем пользователя
        try:
            user_message = f"❌ **ЗАЯВКА ОТКЛОНЕНА**\n\n"
            user_message += f"🆔 Заявка #{request_id}\n"
            user_message += f"📋 План: {plan_name}\n"
            user_message += f"💰 Сумма: {request['amount']} руб.\n\n"
            user_message += f"❗️ Причина отклонения: {reason}\n\n"
            user_message += f"Пожалуйста, проверьте данные и создайте новую заявку."
            
            await context.bot.send_message(
                chat_id=request['telegram_id'],
                text=user_message,
                parse_mode='Markdown'
            )
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления пользователю {request['marzban_username']}: {e}")
        
        await update.message.reply_text(
            f"❌ **Заявка #{request_id} отклонена**\n\n"
            f"👤 Пользователь: `{request['marzban_username']}`\n"
            f"💬 Причина: {reason}",
            parse_mode='Markdown'
        )
    
    def _main_menu_markup(self):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 Главное меню", callback_data="main_menu")]
        ])
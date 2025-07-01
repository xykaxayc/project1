import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "users_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация базы данных и создание таблиц"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица для связи пользователей Marzban с Telegram
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_telegram_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                marzban_username TEXT UNIQUE NOT NULL,
                telegram_id INTEGER UNIQUE,
                telegram_username TEXT,
                phone_number TEXT,
                registration_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                is_verified BOOLEAN DEFAULT FALSE,
                subscription_status TEXT DEFAULT 'active',
                notes TEXT
            )
        ''')
        
        # Таблица для истории платежей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                marzban_username TEXT NOT NULL,
                amount DECIMAL(10,2),
                payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                payment_method TEXT,
                transaction_id TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Таблица для настроек бота
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                setting_key TEXT UNIQUE NOT NULL,
                setting_value TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("База данных инициализирована")
    
    def add_user(self, marzban_username: str, subscription_status: str = 'active', notes: str = None) -> bool:
        """Добавление нового пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO user_telegram_mapping 
                (marzban_username, subscription_status, notes) 
                VALUES (?, ?, ?)
            ''', (marzban_username, subscription_status, notes))
            
            success = cursor.rowcount > 0
            conn.commit()
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка добавления пользователя {marzban_username}: {e}")
            return False
        finally:
            conn.close()
    
    def create_payment_request(self, telegram_id: int, marzban_username: str, plan_id: str, amount: float) -> int:
        """Создание заявки на оплату"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Создаем таблицу для заявок на оплату если её нет
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payment_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER NOT NULL,
                    marzban_username TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    receipt_file_id TEXT,
                    receipt_type TEXT,
                    admin_comment TEXT,
                    processed_at DATETIME,
                    processed_by INTEGER
                )
            ''')
            
            cursor.execute('''
                INSERT INTO payment_requests 
                (telegram_id, marzban_username, plan_id, amount)
                VALUES (?, ?, ?, ?)
            ''', (telegram_id, marzban_username, plan_id, amount))
            
            request_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Создана заявка на оплату #{request_id} для {marzban_username}")
            return request_id
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка создания заявки на оплату: {e}")
            return 0
        finally:
            conn.close()
    
    def add_receipt_to_request(self, request_id: int, file_id: str, file_type: str) -> bool:
        """Добавление чека к заявке на оплату"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE payment_requests 
                SET receipt_file_id = ?, receipt_type = ?
                WHERE id = ?
            ''', (file_id, file_type, request_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Чек добавлен к заявке #{request_id}")
            
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка добавления чека: {e}")
            return False
        finally:
            conn.close()
    
    def get_pending_payment_requests(self):
        """Получение ожидающих обработки заявок"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, telegram_id, marzban_username, plan_id, amount, 
                   created_at, receipt_file_id, receipt_type
            FROM payment_requests 
            WHERE status = 'pending'
            ORDER BY created_at DESC
        ''')
        
        requests = []
        for row in cursor.fetchall():
            requests.append({
                'id': row[0],
                'telegram_id': row[1],
                'marzban_username': row[2],
                'plan_id': row[3],
                'amount': row[4],
                'created_at': row[5],
                'receipt_file_id': row[6],
                'receipt_type': row[7]
            })
        
        conn.close()
        return requests
    
    def approve_payment_request(self, request_id: int, admin_id: int, comment: str = None) -> bool:
        """Одобрение заявки на оплату"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE payment_requests 
                SET status = 'approved', processed_at = CURRENT_TIMESTAMP, 
                    processed_by = ?, admin_comment = ?
                WHERE id = ? AND status = 'pending'
            ''', (admin_id, comment, request_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Заявка #{request_id} одобрена админом {admin_id}")
            
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка одобрения заявки: {e}")
            return False
        finally:
            conn.close()
    
    def reject_payment_request(self, request_id: int, admin_id: int, comment: str) -> bool:
        """Отклонение заявки на оплату"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE payment_requests 
                SET status = 'rejected', processed_at = CURRENT_TIMESTAMP, 
                    processed_by = ?, admin_comment = ?
                WHERE id = ? AND status = 'pending'
            ''', (admin_id, comment, request_id))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Заявка #{request_id} отклонена админом {admin_id}")
            
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка отклонения заявки: {e}")
            return False
        finally:
            conn.close()
    
    def get_payment_request(self, request_id: int):
        """Получение заявки по ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, telegram_id, marzban_username, plan_id, amount, 
                   created_at, status, receipt_file_id, receipt_type
            FROM payment_requests 
            WHERE id = ?
        ''', (request_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'telegram_id': row[1],
                'marzban_username': row[2],
                'plan_id': row[3],
                'amount': row[4],
                'created_at': row[5],
                'status': row[6],
                'receipt_file_id': row[7],
                'receipt_type': row[8]
            }
        return None
    
    def create_new_user_record(self, username: str, telegram_id: int, telegram_username: str = None) -> bool:
        """Создание записи для нового зарегистрированного пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Формируем примечание для нового пользователя
            note_parts = [f"Telegram ID: {telegram_id}"]
            if telegram_username:
                note_parts.append(f"@{telegram_username}")
            note_parts.append("Зарегистрирован через бота")
            notes = " | ".join(note_parts)
            
            cursor.execute('''
                INSERT INTO user_telegram_mapping 
                (marzban_username, telegram_id, telegram_username, is_verified, 
                 subscription_status, notes) 
                VALUES (?, ?, ?, TRUE, 'active', ?)
            ''', (username, telegram_id, telegram_username, notes))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Запись для нового пользователя {username} создана")
            
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка создания записи пользователя: {e}")
            return False
        finally:
            conn.close()
    
    def get_users_by_telegram_id_partial(self, telegram_id: int):
        """Получение всех пользователей (связанных и несвязанных) для конкретного Telegram ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT marzban_username, telegram_id, subscription_status, is_verified
            FROM user_telegram_mapping 
            WHERE telegram_id = ? OR telegram_id IS NULL
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        # Возвращаем связанные с этим telegram_id
        linked_users = []
        for row in results:
            if row[1] == telegram_id:  # telegram_id совпадает
                linked_users.append({
                    'marzban_username': row[0],
                    'telegram_id': row[1],
                    'subscription_status': row[2],
                    'is_verified': bool(row[3])
                })
        
        return linked_users
    
    def get_users_by_telegram_id(self, telegram_id: int) -> List[Dict]:
        """Получение всех аккаунтов пользователя по Telegram ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT marzban_username, telegram_id, telegram_username, 
                   subscription_status, registration_date, is_verified, notes
            FROM user_telegram_mapping 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        rows = cursor.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                'marzban_username': row[0],
                'telegram_id': row[1],
                'telegram_username': row[2],
                'subscription_status': row[3],
                'registration_date': row[4],
                'is_verified': bool(row[5]),
                'notes': row[6]
            })
        return result
    
    def add_telegram_id_to_notes(self, marzban_username: str, telegram_id: int) -> bool:
        """Добавление Telegram ID в примечания пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Получаем текущие примечания
            cursor.execute(
                "SELECT notes FROM user_telegram_mapping WHERE marzban_username = ?",
                (marzban_username,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False
            
            current_notes = result[0] or ""
            
            # Проверяем, нет ли уже Telegram ID в примечаниях
            if f"Telegram ID: {telegram_id}" in current_notes:
                logger.info(f"Telegram ID {telegram_id} уже есть в примечаниях для {marzban_username}")
                return True
            
            # Добавляем Telegram ID к существующим примечаниям
            if current_notes:
                new_notes = f"{current_notes} | Telegram ID: {telegram_id}"
            else:
                new_notes = f"Telegram ID: {telegram_id}"
            
            cursor.execute('''
                UPDATE user_telegram_mapping 
                SET notes = ?
                WHERE marzban_username = ?
            ''', (new_notes, marzban_username))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Telegram ID {telegram_id} добавлен в примечания для {marzban_username}")
            
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка обновления примечаний: {e}")
            return False
        finally:
            conn.close()
    
    def update_user_notes(self, marzban_username: str, notes: str) -> bool:
        """Обновление примечаний пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE user_telegram_mapping 
                SET notes = ?
                WHERE marzban_username = ?
            ''', (notes, marzban_username))
            
            success = cursor.rowcount > 0
            conn.commit()
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка обновления примечаний: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Получение пользователя по Telegram ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT marzban_username, telegram_id, telegram_username, 
                   subscription_status, registration_date, is_verified, notes
            FROM user_telegram_mapping 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'marzban_username': row[0],
                'telegram_id': row[1],
                'telegram_username': row[2],
                'subscription_status': row[3],
                'registration_date': row[4],
                'is_verified': bool(row[5]),
                'notes': row[6]
            }
        return None
    
    def get_user_by_marzban_username(self, marzban_username: str) -> Optional[Dict]:
        """Получение пользователя по имени в Marzban"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT marzban_username, telegram_id, telegram_username, 
                   subscription_status, registration_date, is_verified, notes
            FROM user_telegram_mapping 
            WHERE marzban_username = ?
        ''', (marzban_username,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'marzban_username': row[0],
                'telegram_id': row[1],
                'telegram_username': row[2],
                'subscription_status': row[3],
                'registration_date': row[4],
                'is_verified': bool(row[5]),
                'notes': row[6]
            }
        return None
    
    def link_telegram_account(self, marzban_username: str, telegram_id: int, 
                             telegram_username: str = None, phone_number: str = None) -> bool:
        """Связывание аккаунта Marzban с Telegram"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Формируем примечание с Telegram ID
            note_parts = [f"Telegram ID: {telegram_id}"]
            if telegram_username:
                note_parts.append(f"@{telegram_username}")
            note_parts.append("Связан через бота")
            notes = " | ".join(note_parts)
            
            cursor.execute('''
                UPDATE user_telegram_mapping 
                SET telegram_id = ?, telegram_username = ?, phone_number = ?, 
                    is_verified = TRUE, notes = ?
                WHERE marzban_username = ? AND telegram_id IS NULL
            ''', (telegram_id, telegram_username, phone_number, notes, marzban_username))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            if success:
                logger.info(f"Пользователь {marzban_username} связан с Telegram ID {telegram_id}")
            
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка связывания аккаунта: {e}")
            return False
        finally:
            conn.close()
    
    def get_unlinked_users(self) -> List[str]:
        """Получение списка пользователей без связанного Telegram ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT marzban_username FROM user_telegram_mapping 
            WHERE telegram_id IS NULL
        ''')
        
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users
    
    def record_payment(self, telegram_id: int, marzban_username: str, amount: float, 
                      payment_method: str, transaction_id: str = None, status: str = 'completed') -> bool:
        """Запись платежа в историю"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if not transaction_id:
                transaction_id = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            cursor.execute('''
                INSERT INTO payment_history 
                (telegram_id, marzban_username, amount, payment_method, transaction_id, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (telegram_id, marzban_username, amount, payment_method, transaction_id, status))
            
            conn.commit()
            logger.info(f"Платеж записан: {marzban_username} - {amount} руб.")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка записи платежа: {e}")
            return False
        finally:
            conn.close()
    
    def get_payment_history(self, telegram_id: int = None, marzban_username: str = None, 
                           limit: int = 10) -> List[Dict]:
        """Получение истории платежей"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if telegram_id:
            cursor.execute('''
                SELECT telegram_id, marzban_username, amount, payment_date, 
                       payment_method, transaction_id, status
                FROM payment_history 
                WHERE telegram_id = ?
                ORDER BY payment_date DESC
                LIMIT ?
            ''', (telegram_id, limit))
        elif marzban_username:
            cursor.execute('''
                SELECT telegram_id, marzban_username, amount, payment_date, 
                       payment_method, transaction_id, status
                FROM payment_history 
                WHERE marzban_username = ?
                ORDER BY payment_date DESC
                LIMIT ?
            ''', (marzban_username, limit))
        else:
            cursor.execute('''
                SELECT telegram_id, marzban_username, amount, payment_date, 
                       payment_method, transaction_id, status
                FROM payment_history 
                ORDER BY payment_date DESC
                LIMIT ?
            ''', (limit,))
        
        payments = []
        for row in cursor.fetchall():
            payments.append({
                'telegram_id': row[0],
                'marzban_username': row[1],
                'amount': row[2],
                'payment_date': row[3],
                'payment_method': row[4],
                'transaction_id': row[5],
                'status': row[6]
            })
        
        conn.close()
        return payments
    
    def get_statistics(self) -> Dict:
        """Получение статистики базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Статистика пользователей
        cursor.execute("SELECT COUNT(*) FROM user_telegram_mapping")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_telegram_mapping WHERE telegram_id IS NOT NULL")
        linked_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM user_telegram_mapping WHERE is_verified = TRUE")
        verified_users = cursor.fetchone()[0]
        
        # Статистика платежей
        cursor.execute("SELECT COUNT(*), SUM(amount) FROM payment_history WHERE status = 'completed'")
        payment_stats = cursor.fetchone()
        total_payments = payment_stats[0] or 0
        total_revenue = payment_stats[1] or 0
        
        # Платежи за последний месяц
        cursor.execute('''
            SELECT COUNT(*), SUM(amount) 
            FROM payment_history 
            WHERE status = 'completed' 
            AND datetime(payment_date) >= datetime('now', '-30 days')
        ''')
        monthly_stats = cursor.fetchone()
        monthly_payments = monthly_stats[0] or 0
        monthly_revenue = monthly_stats[1] or 0
        
        conn.close()
        
        return {
            'total_users': total_users,
            'linked_users': linked_users,
            'verified_users': verified_users,
            'unlinked_users': total_users - linked_users,
            'link_percentage': (linked_users / total_users * 100) if total_users > 0 else 0,
            'total_payments': total_payments,
            'total_revenue': total_revenue,
            'monthly_payments': monthly_payments,
            'monthly_revenue': monthly_revenue
        }
    
    def update_user_status(self, marzban_username: str, status: str) -> bool:
        """Обновление статуса пользователя"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE user_telegram_mapping 
                SET subscription_status = ?
                WHERE marzban_username = ?
            ''', (status, marzban_username))
            
            success = cursor.rowcount > 0
            conn.commit()
            return success
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка обновления статуса пользователя: {e}")
            return False
        finally:
            conn.close()
    
    def get_setting(self, key: str) -> Optional[str]:
        """Получение настройки бота"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT setting_value FROM bot_settings WHERE setting_key = ?", (key,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def set_setting(self, key: str, value: str) -> bool:
        """Установка настройки бота"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO bot_settings (setting_key, setting_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Ошибка сохранения настройки: {e}")
            return False
        finally:
            conn.close()
    
    def delete_user_by_username(self, marzban_username: str) -> bool:
        """Удалить пользователя по marzban_username"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_telegram_mapping WHERE marzban_username = ?", (marzban_username,))
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return deleted
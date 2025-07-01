import requests
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from enums import UserStatus
from text_constants import SUBSCRIPTION_FORMATS, API_PROVIDED_DESCRIPTION, NO_VPN_CONFIG_ERROR, API_PROVIDED_SOURCE

logger = logging.getLogger(__name__)

class MarzbanAPI:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url: str = base_url.rstrip('/')
        self.username: str = username
        self.password: str = password
        self.token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self._cached_subscription_format: Optional[str] = None  # Кешируем рабочий формат
    
    def authenticate(self) -> bool:
        """Аутентификация и получение токена"""
        try:
            # Используем правильный эндпоинт для авторизации
            response = requests.post(
                f"{self.base_url}/api/admin/token",
                data={"username": self.username, "password": self.password},
                timeout=30
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.token = token_data['access_token']
            self.token_expires = datetime.now() + timedelta(minutes=25)
            
            logger.info("Успешная аутентификация в Marzban")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка аутентификации Marzban: {e}")
            return False
    
    def get_user_subscription_url(self, username: str) -> Optional[str]:
        """Получение ссылки подписки пользователя через API"""
        if not self._ensure_authenticated():
            return None
        
        try:
            # Используем правильный эндпоинт для получения данных пользователя
            response = requests.get(
                f"{self.base_url}/api/user/{username}",
                headers=self.get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            user_data = response.json()
            subscription_url = user_data.get('subscription_url')
            
            if subscription_url:
                logger.info(f"Получена subscription_url из API для {username}: {subscription_url}")
                return subscription_url
            else:
                logger.warning(f"subscription_url не найдена в ответе API для {username}")
                # Пробуем сформировать ссылку вручную
                return self._generate_subscription_url(username)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка получения subscription_url для {username}: {e}")
            # Пробуем сформировать ссылку вручную как fallback
            return self._generate_subscription_url(username)
    
    def _generate_subscription_url(self, username: str) -> Optional[str]:
        """Генерация ссылки подписки если API не вернул её"""
        # Пробуем стандартные форматы Marzban
        possible_formats = [
            f"{self.base_url}/sub/{username}",
            f"{self.base_url}/sub/{username}?token={self.token}",
            f"{self.base_url}/subscription/{username}",
            f"{self.base_url}/api/subscription/{username}",
        ]
        
        for url in possible_formats:
            if self._test_url(url):
                logger.info(f"Сгенерированная рабочая ссылка для {username}: {url}")
                return url
        
        logger.error(f"Не удалось сгенерировать рабочую ссылку для {username}")
        return None
    
    def _test_url(self, url: str) -> bool:
        """Быстрая проверка работоспособности URL"""
        try:
            response = requests.head(url, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_subscription_formats(self, username: str) -> List[Dict[str, str]]:
        """Получение всех возможных форматов ссылок подписки"""
        formats = []
        for fmt in SUBSCRIPTION_FORMATS:
            formats.append({
                "name": fmt["name"],
                "url": fmt["url"].format(base_url=self.base_url, username=username, token=self.token),
                "description": fmt["description"]
            })
        return formats
    
    def test_subscription_url(self, username: str) -> Dict[str, Dict[str, Any]]:
        """Тестирование всех возможных форматов ссылок подписки"""
        formats = self.get_subscription_formats(username)
        results = {}
        
        logger.info(f"Тестирование ссылок подписки для пользователя {username}")
        
        # Сначала пробуем получить ссылку из API
        api_subscription_url = self.get_user_subscription_url(username)
        if api_subscription_url:
            results["api_provided"] = {
                "url": api_subscription_url,
                "status_code": 200,
                "works": True,
                "source": API_PROVIDED_SOURCE,
                "description": API_PROVIDED_DESCRIPTION
            }
            logger.info(f"✅ API предоставил ссылку: {api_subscription_url}")
        
        # Затем тестируем стандартные форматы
        for format_info in formats:
            name = format_info["name"]
            url = format_info["url"]
            
            try:
                # Тестируем HEAD запрос
                response = requests.head(url, timeout=10, allow_redirects=True)
                
                if response.status_code == 200:
                    # Дополнительно проверяем GET запрос для подтверждения
                    get_response = requests.get(url, timeout=10, allow_redirects=True)
                    
                    # Проверяем, что ответ содержит конфигурацию VPN
                    content = get_response.text.lower()
                    has_vpn_config = any(keyword in content for keyword in [
                        'vless://', 'vmess://', 'trojan://', 'ss://', 'ssr://',
                        'hysteria://', 'tuic://', 'shadowsocks://', 'wireguard:'
                    ])
                    
                    if has_vpn_config and len(get_response.text) > 10:
                        results[name] = {
                            "url": url,
                            "status_code": response.status_code,
                            "works": True,
                            "content_length": len(get_response.text),
                            "has_config": True,
                            "description": format_info["description"]
                        }
                        logger.info(f"✅ Рабочая ссылка найдена: {name} -> {url}")
                    else:
                        results[name] = {
                            "url": url,
                            "status_code": response.status_code,
                            "works": False,
                            "error": NO_VPN_CONFIG_ERROR,
                            "description": format_info["description"]
                        }
                else:
                    results[name] = {
                        "url": url,
                        "status_code": response.status_code,
                        "works": False,
                        "error": f"HTTP {response.status_code}",
                        "description": format_info["description"]
                    }
                    
            except requests.exceptions.RequestException as e:
                results[name] = {
                    "url": url,
                    "works": False,
                    "error": str(e),
                    "description": format_info["description"]
                }
                logger.debug(f"❌ {name}: {e}")
        
        return results
    
    def get_working_subscription_url(self, username: str) -> Optional[str]:
        """Получение рабочей ссылки подписки с приоритетом API"""
        # Сначала пробуем получить из API
        api_url = self.get_user_subscription_url(username)
        if api_url and self._test_url(api_url):
            logger.info(f"Используем ссылку из API: {api_url}")
            return api_url
        
        # Если API не дал ссылку или она не работает, тестируем форматы
        if self._cached_subscription_format:
            cached_url = self._cached_subscription_format.replace("{username}", username)
            if self._test_url(cached_url):
                logger.debug(f"Используем кешированный формат: {cached_url}")
                return cached_url
            else:
                logger.info("Кешированный формат больше не работает, ищем новый")
                self._cached_subscription_format = None
        
        # Тестируем все форматы
        test_results = self.test_subscription_url(username)
        
        # Приоритет для API
        if "api_provided" in test_results and test_results["api_provided"].get('works', False):
            return test_results["api_provided"]['url']
        
        # Ищем первый рабочий формат
        for name, result in test_results.items():
            if result.get('works', False) and name != "api_provided":
                # Кешируем рабочий формат
                self._cached_subscription_format = result['url'].replace(username, "{username}")
                logger.info(f"Найден и закеширован рабочий формат: {name}")
                return result['url']
        
        logger.warning(f"Не найдено рабочих ссылок подписки для {username}")
        return None
    
    def get_user_connection_info(self, username: str) -> Optional[Dict[str, Any]]:
        """Получение информации для подключения пользователя"""
        user_info = self.get_user(username)
        if not user_info:
            return None
        
        # Получаем ссылку подписки (сначала из API, потом пробуем форматы)
        subscription_url = self.get_working_subscription_url(username)
        
        if not subscription_url:
            logger.error(f"Не удалось получить рабочую ссылку подписки для {username}")
            return None
        
        connection_info = {
            "username": username,
            "status": user_info.get("status"),
            "protocols": list(user_info.get("proxies", {}).keys()),
            "subscription_url": subscription_url,
            "qr_code_url": f"{subscription_url}&format=qr",
            "clash_url": f"{subscription_url}&format=clash",
            "v2ray_url": f"{subscription_url}&format=v2ray"
        }
        
        return connection_info
    
    def verify_subscription_url(self, url: str) -> Dict[str, Any]:
        """Детальная проверка ссылки подписки"""
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                return {
                    "valid": False,
                    "error": f"HTTP {response.status_code}",
                    "details": response.text[:200] if response.text else "Нет содержимого"
                }
            
            content = response.text
            
            # Проверяем наличие VPN конфигураций
            vpn_protocols = {
                'vless://': 'VLESS',
                'vmess://': 'VMess', 
                'trojan://': 'Trojan',
                'ss://': 'Shadowsocks',
                'ssr://': 'ShadowsocksR',
                'hysteria://': 'Hysteria',
                'tuic://': 'TUIC'
            }
            
            found_protocols = []
            for protocol, name in vpn_protocols.items():
                if protocol in content.lower():
                    found_protocols.append(name)
            
            if not found_protocols:
                return {
                    "valid": False,
                    "error": NO_VPN_CONFIG_ERROR,
                    "content_preview": content[:200] if content else "Пустой ответ",
                    "content_length": len(content)
                }
            
            # Подсчитываем количество конфигураций
            config_count = sum(content.count(protocol) for protocol in vpn_protocols.keys())
            
            return {
                "valid": True,
                "protocols": found_protocols,
                "config_count": config_count,
                "content_length": len(content),
                "response_time": response.elapsed.total_seconds()
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "valid": False,
                "error": f"Ошибка запроса: {str(e)}"
            }
    
    def create_new_user(self, username: str, protocols: List[str] = None, trial_days: int = 0, data_limit_gb: float = None, note: str = "") -> Tuple[bool, str]:
        """Создание нового пользователя с пробным периодом и возвратом причины ошибки (структура максимально близка к ручному примеру)"""
        if not self._ensure_authenticated():
            return False, "Ошибка аутентификации API"
        try:
            if not protocols:
                protocols = ["vless"]
            proxies = {}
            for protocol in protocols:
                proto = protocol.lower()
                if proto == "vless":
                    proxies["vless"] = {"flow": "xtls-rprx-vision"}  # flow по умолчанию, если требуется
                elif proto == "vmess":
                    proxies["vmess"] = {}
                elif proto == "trojan":
                    proxies["trojan"] = {}
                elif proto == "shadowsocks":
                    proxies["shadowsocks"] = {}
            if not proxies:
                proxies = {"vless": {"flow": "xtls-rprx-vision"}}
            user_data = {
                "username": username,
                "proxies": proxies,
                "status": "active",
                "note": note or f"Created by bot at {datetime.now().isoformat()}"
            }
            if data_limit_gb:
                user_data["data_limit"] = int(data_limit_gb * 1024 * 1024 * 1024)
            if trial_days > 0:
                expire_date = datetime.now() + timedelta(days=trial_days)
                user_data["expire"] = int(expire_date.timestamp())
            logger.info(f"Создание пользователя {username} с настройками: {user_data}")
            response = requests.post(
                f"{self.base_url}/api/user",
                headers=self.get_headers(),
                json=user_data,
                timeout=30
            )
            if response.status_code == 200:
                logger.info(f"Пользователь {username} создан успешно")
                self._cached_subscription_format = None
                import time
                for attempt in range(3):
                    user_info = self.get_user(username)
                    if user_info:
                        return True, ""
                    time.sleep(1)
                logger.error(f"Пользователь {username} не появился в выдаче Marzban после создания!")
                return False, "Пользователь не появился в выдаче Marzban после создания. Попробуйте позже или обратитесь к администратору."
            else:
                logger.error(f"Ошибка {response.status_code} при создании пользователя {username}: {response.text}")
                return False, f"Ошибка {response.status_code}: {response.text}"
        except Exception as e:
            logger.error(f"Ошибка создания пользователя {username}: {e}")
            return False, str(e)
    
    def check_username_availability(self, username: str) -> bool:
        """Проверка доступности логина"""
        user_info = self.get_user(username)
        return user_info is None
    
    def update_user_note(self, username: str, note: str) -> bool:
        """Обновление примечания пользователя в Marzban"""
        if not self._ensure_authenticated():
            return False
        
        try:
            current_user = self.get_user(username)
            if not current_user:
                logger.error(f"Пользователь {username} не найден")
                return False
            
            current_note = current_user.get('note') or ''
            
            if current_note and 'Telegram ID:' in current_note:
                import re
                new_note = re.sub(r'Telegram ID: \d+[^|]*', note.strip(), current_note)
                if new_note == current_note:
                    new_note = f"{current_note} | {note}" if current_note else note
            else:
                new_note = f"{current_note} | {note}" if current_note else note
            
            update_data = {'note': new_note.strip()}
            
            logger.info(f"Обновление примечания для {username}: {new_note}")
            
            response = requests.patch(
                f"{self.base_url}/api/user/{username}",
                headers=self.get_headers(),
                json=update_data,
                timeout=30
            )
            
            if response.status_code == 405:
                logger.info(f"PATCH не поддерживается, используем PUT для {username}")
                
                full_update_data = {
                    'username': current_user.get('username'),
                    'proxies': current_user.get('proxies', {}),
                    'status': current_user.get('status', 'active'),
                    'note': new_note.strip()
                }
                
                if 'expire' in current_user:
                    full_update_data['expire'] = current_user['expire']
                if 'data_limit' in current_user:
                    full_update_data['data_limit'] = current_user['data_limit']
                
                response = requests.put(
                    f"{self.base_url}/api/user/{username}",
                    headers=self.get_headers(),
                    json=full_update_data,
                    timeout=30
                )
            
            if response.status_code != 200:
                logger.error(f"Ошибка {response.status_code} при обновлении примечания {username}: {response.text}")
                return False
            
            logger.info(f"Примечание для {username} обновлено успешно")
            return True
            
        except requests.exceptions.Timeout:
            logger.error(f"Таймаут при обновлении примечания для {username}")
            return False
        except Exception as e:
            logger.error(f"Ошибка обновления примечания для {username}: {e}")
            return False
    
    def sync_telegram_id_to_marzban_notes(self, username: str, telegram_id: int, telegram_username: Optional[str] = None) -> bool:
        """Синхронизация Telegram ID в примечания Marzban"""
        note_parts = [f"Telegram ID: {telegram_id}"]
        if telegram_username:
            note_parts.append(f"@{telegram_username}")
        
        note = " | ".join(note_parts)
        return self.update_user_note(username, note)
    
    def _ensure_authenticated(self) -> bool:
        """Проверка и обновление токена при необходимости"""
        if not self.token or (self.token_expires and datetime.now() >= self.token_expires):
            return self.authenticate()
        return True
    
    def get_headers(self) -> Dict[str, str]:
        """Получение заголовков для API запросов"""
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    def get_all_users(self, offset: int = 0, limit: int = 1000) -> Optional[List[Dict[str, Any]]]:
        """Получение всех пользователей"""
        if not self._ensure_authenticated():
            return None
        
        try:
            response = requests.get(
                f"{self.base_url}/api/users",
                headers=self.get_headers(),
                params={'offset': offset, 'limit': limit},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get('users', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            return None
    
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Получение информации о конкретном пользователе"""
        if not self._ensure_authenticated():
            return None
        
        try:
            response = requests.get(
                f"{self.base_url}/api/user/{username}",
                headers=self.get_headers(),
                timeout=30
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка получения пользователя {username}: {e}")
            return None
    
    def extend_user_subscription(self, username: str, days: int) -> bool:
        """Продление подписки пользователя на указанное количество дней"""
        logger.info(f"Попытка продлить подписку для {username} на {days} дней")
        
        user_info = self.get_user(username)
        if not user_info:
            logger.error(f"Не удалось получить информацию о пользователе {username}")
            return False
        
        try:
            current_expire = user_info.get('expire')
            current_status = user_info.get('status')
            
            logger.info(f"Текущий статус {username}: {current_status}, текущий expire: {current_expire}")
            
            if current_expire and current_expire > int(datetime.now().timestamp()):
                new_expire = current_expire + (days * 24 * 60 * 60)
                logger.info(f"Продление существующей подписки до {datetime.fromtimestamp(new_expire)}")
            else:
                new_expire = int((datetime.now() + timedelta(days=days)).timestamp())
                logger.info(f"Новая подписка до {datetime.fromtimestamp(new_expire)}")
            
            success = self.update_user(username, expire=new_expire, status="active")
            
            if success:
                logger.info(f"Подписка для {username} успешно продлена на {days} дней")
            else:
                logger.error(f"Не удалось продлить подписку для {username}")
                
            return success
            
        except Exception as e:
            logger.error(f"Ошибка продления подписки для {username}: {e}")
            return False
    
    def update_user(self, username: str, **kwargs) -> bool:
        """Обновление пользователя"""
        if not self._ensure_authenticated():
            return False
        
        try:
            current_user = self.get_user(username)
            if not current_user:
                logger.error(f"Пользователь {username} не найден")
                return False
            
            current_proxies = current_user.get('proxies', {})
            
            filtered_proxies = {}
            for proxy_type, proxy_config in current_proxies.items():
                if proxy_type.lower() != 'trojan':
                    filtered_proxies[proxy_type] = proxy_config
                else:
                    logger.warning(f"Пропускаем протокол trojan для пользователя {username}")
            
            if not filtered_proxies:
                filtered_proxies = {'vless': {}}
                logger.info(f"Использованы протоколы по умолчанию для {username}")
            
            update_data = {
                'username': current_user.get('username'),
                'proxies': filtered_proxies,
                'status': kwargs.get('status', current_user.get('status', 'active'))
            }
            
            if 'expire' in kwargs:
                update_data['expire'] = kwargs['expire']
            elif 'expire' in current_user:
                update_data['expire'] = current_user['expire']
            
            if 'data_limit' in kwargs:
                update_data['data_limit'] = kwargs['data_limit']
            elif 'data_limit' in current_user:
                update_data['data_limit'] = current_user['data_limit']
            
            if 'used_traffic' in kwargs:
                update_data['used_traffic'] = kwargs['used_traffic']
            
            logger.debug(f"Обновление пользователя {username} с данными: {update_data}")
            
            response = requests.put(
                f"{self.base_url}/api/user/{username}",
                headers=self.get_headers(),
                json=update_data,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Ошибка {response.status_code} при обновлении {username}: {response.text}")
                return False
            
            logger.info(f"Пользователь {username} обновлен успешно")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети при обновлении пользователя {username}: {e}")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при обновлении пользователя {username}: {e}")
            return False
    
    def get_user_usage_stats(self, username: str) -> Optional[Dict[str, Any]]:
        """Получение детальной статистики использования пользователя"""
        user_info = self.get_user(username)
        if not user_info:
            return None
        
        used_traffic = user_info.get('used_traffic', 0)
        data_limit = user_info.get('data_limit', 0)
        expire = user_info.get('expire')
        
        # Обеспечиваем что значения не None
        if used_traffic is None:
            used_traffic = 0
        if data_limit is None:
            data_limit = 0
            
        stats = {
            'username': username,
            'used_traffic_bytes': used_traffic,
            'data_limit_bytes': data_limit,
            'used_traffic_gb': used_traffic / (1024**3) if used_traffic else 0,
            'data_limit_gb': data_limit / (1024**3) if data_limit else 0,
            'traffic_percentage': (used_traffic / data_limit * 100) if data_limit and data_limit > 0 else 0,
            'status': user_info.get('status', 'unknown'),
            'expire_timestamp': expire,
            'is_expired': False,
            'days_remaining': None
        }
        
        if expire and expire > 0:  # Проверяем что expire не None и больше 0
            try:
                expire_date = datetime.fromtimestamp(expire)
                now = datetime.now()
                
                if expire_date < now:
                    stats['is_expired'] = True
                    stats['days_remaining'] = 0
                else:
                    days_diff = (expire_date - now).days
                    stats['days_remaining'] = max(0, days_diff)  # Не меньше 0
            except (ValueError, OSError) as e:
                logger.warning(f"Ошибка обработки времени истечения для {username}: {e}")
                stats['expire_timestamp'] = None
                stats['is_expired'] = False
                stats['days_remaining'] = None
        
        return stats
    
    @staticmethod
    def bytes_to_human(bytes_val: int) -> str:
        """Конвертация байтов в читаемый формат с экранированием точки для MarkdownV2"""
        if bytes_val == 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                # Экранируем точку для MarkdownV2
                return f"{bytes_val:.1f}".replace('.', '\\.') + f" {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f}".replace('.', '\\.') + " PB"

    def get_subscription_days_left(self, expire_date_str: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Возвращает количество дней до истечения подписки и строку с датой истечения.
        :param expire_date_str: строка с датой истечения (ISO 8601 или timestamp)
        :return: (days_left: int | None, expire_date_str: str | None)
        """
        if not expire_date_str:
            return None, None
        try:
            # Пробуем ISO 8601
            expire_date = datetime.fromisoformat(expire_date_str.replace('Z', '+00:00'))
        except Exception:
            try:
                # Пробуем timestamp (секунды)
                expire_date = datetime.utcfromtimestamp(int(expire_date_str))
            except Exception:
                return None, expire_date_str
        now = datetime.utcnow()
        days_left = (expire_date - now).days
        # Экранируем точки для MarkdownV2
        expire_date_str_md = expire_date.strftime('%d.%m.%Y').replace('.', '\\.')
        return days_left, expire_date_str_md

    def format_data_limit(self, data_limit: Any) -> str:
        """
        Форматирует лимит трафика в ГБ для отображения пользователю.
        :param data_limit: лимит в байтах, мегабайтах, гигабайтах или None
        :return: строка с лимитом или 'Без лимита'
        """
        if data_limit is None:
            return 'Без лимита'
        try:
            data_limit = float(data_limit)
            if data_limit == 0:
                return 'Без лимита'
            elif data_limit > 1024:
                # Экранируем точку
                return f"{data_limit/1024:.2f}".replace('.', '\\.') + ' ГБ'
            else:
                return f"{data_limit:.2f}".replace('.', '\\.') + ' МБ'
        except Exception:
            return str(data_limit)

    def format_used_traffic(self, used_traffic: Any) -> str:
        """
        Форматирует использованный трафик в ГБ для отображения пользователю.
        :param used_traffic: использовано в байтах, мегабайтах, гигабайтах или None
        :return: строка с объемом
        """
        if used_traffic is None:
            return '0 МБ'
        try:
            used_traffic = float(used_traffic)
            if used_traffic > 1024:
                return f"{used_traffic/1024:.2f}".replace('.', '\\.') + ' ГБ'
            else:
                return f"{used_traffic:.2f}".replace('.', '\\.') + ' МБ'
        except Exception:
            return str(used_traffic)
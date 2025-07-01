import os
import json
from typing import Dict, Any

class TextManager:
    """Менеджер для работы с текстовыми сообщениями"""
    
    def __init__(self):
        self.base_path = os.path.dirname(__file__)
        self._cache = {}
        self._load_all_texts()
    
    def _load_text_file(self, path: str) -> Dict[str, str]:
        """Загрузка текстового файла с сообщениями"""
        messages = {}
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    messages[key] = value
                else:
                    messages[os.path.splitext(os.path.basename(path))[0]] = line.strip()
        return messages
    
    def _load_json_file(self, path: str) -> Dict[str, Any]:
        """Загрузка JSON файла"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_all_texts(self):
        """Загрузка всех текстовых файлов"""
        for root, _, files in os.walk(self.base_path):
            for file in files:
                if file.endswith('.txt'):
                    relative_path = os.path.relpath(root, self.base_path)
                    category = relative_path.replace(os.sep, '.') if relative_path != '.' else ''
                    messages = self._load_text_file(os.path.join(root, file))
                    for key, value in messages.items():
                        full_key = f"{category}.{key}" if category else key
                        self._cache[full_key] = value
                elif file.endswith('.json'):
                    relative_path = os.path.relpath(root, self.base_path)
                    category = relative_path.replace(os.sep, '.') if relative_path != '.' else ''
                    data = self._load_json_file(os.path.join(root, file))
                    key = os.path.splitext(file)[0]
                    full_key = f"{category}.{key}" if category else key
                    self._cache[full_key] = data
    
    def get(self, key: str, **kwargs) -> str:
        """Получение текста по ключу с форматированием"""
        text = self._cache.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except KeyError as e:
                return f"Missing format key: {e}"
            except Exception as e:
                return f"Format error: {e}"
        return text
    
    def get_json(self, key: str) -> Dict[str, Any]:
        """Получение данных из JSON файла"""
        return self._cache.get(key, {})

# Создаем глобальный экземпляр
text_manager = TextManager()

# Экспортируем функцию для удобного доступа
def get_text(key: str, **kwargs) -> str:
    return text_manager.get(key, **kwargs)

def get_json(key: str) -> Dict[str, Any]:
    return text_manager.get_json(key)

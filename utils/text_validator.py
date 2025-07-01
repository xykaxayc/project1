"""
Модуль для валидации текстовых сообщений в проекте.
Помогает обнаружить жёстко заданные строки, которые следует вынести в текстовые файлы.
"""

import os
import ast
import re
from typing import List, Tuple, Set

def should_ignore_string(text: str, node: ast.AST) -> bool:
    """
    Определяет, следует ли игнорировать строку при проверке.
    
    Args:
        text: Строка для проверки
        node: AST узел строки
    """
    # Игнорируем docstrings
    if isinstance(node.parent, (ast.Module, ast.ClassDef, ast.FunctionDef)):
        return True
        
    # Игнорируем логи
    if 'log' in text.lower() or text.startswith(('DEBUG:', 'INFO:', 'WARNING:', 'ERROR:')):
        return True
        
    # Игнорируем технические строки
    if any([
        text.startswith(('def ', 'class ', 'import ', 'from ', 'raise ', '@')),  # Код
        text.startswith(('http://', 'https://', 'git://', 'file://')),  # URLs
        text.startswith(('#', '//', '/*', '*/')),  # Комментарии
        re.match(r'^[\w\-\.]+\.[a-zA-Z]+$', text),  # Имена файлов
        re.match(r'^[a-zA-Z_]\w*$', text),  # Идентификаторы
        re.match(r'^[\[\]\(\)\{\}.,;:\'\"\\/<>!@#$%^&*+=|~`]', text),  # Синтаксис
        re.match(r'^(?:[0-9]+|0x[0-9a-fA-F]+)$', text),  # Числа
        re.match(r'^\s*$', text),  # Пустые строки
        len(text) < 10  # Короткие строки
    ]):
        return True
        
    return False

def is_user_facing_message(text: str) -> bool:
    """
    Определяет, является ли строка сообщением для пользователя.
    """
    # Ищем признаки сообщения пользователю
    message_indicators = [
        re.search(r'[а-яА-Я]', text),  # Кириллица
        any(char in text for char in '.,!?:;'),  # Знаки препинания
        any(emoji in text for emoji in '🔄✅❌⚠️🚫⏳❓📊👤💳📱'),  # Эмодзи
        re.search(r'[\'"](.*?)[\'"]', text),  # Текст в кавычках
        '%' in text and any(x in text for x in ('s', 'd', 'f')),  # Форматирование
        '{' in text and '}' in text  # f-строки
    ]
    
    return any(message_indicators)

def find_hardcoded_strings(file_path: str) -> List[Tuple[int, str]]:
    """
    Поиск потенциально жёстко заданных строк в Python файле.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    tree = ast.parse(content)
    strings = []
    
    class StringFinder(ast.NodeVisitor):
        def visit_Constant(self, node):
            if isinstance(node.value, str):
                text = node.value.strip()
                if not should_ignore_string(text, node) and is_user_facing_message(text):
                    strings.append((node.lineno, text))
            self.generic_visit(node)
            
        def visit_Str(self, node):
            # Для обратной совместимости с Python < 3.8
            text = node.s.strip()
            if not should_ignore_string(text, node) and is_user_facing_message(text):
                strings.append((node.lineno, text))
            self.generic_visit(node)
    
    finder = StringFinder()
    finder.visit(tree)
    return strings

def validate_project_texts(project_root: str) -> List[str]:
    """
    Валидация всех Python файлов в проекте на наличие жёстко заданных строк.
    """
    warnings = []
    excluded_dirs = {'__pycache__', 'venv', '.git', '.idea', '.vscode'}
    
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in excluded_dirs]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    hardcoded = find_hardcoded_strings(file_path)
                    if hardcoded:
                        rel_path = os.path.relpath(file_path, project_root)
                        for line_no, text in hardcoded:
                            # Ограничиваем длину текста для вывода
                            display_text = text[:50] + '...' if len(text) > 50 else text
                            # Экранируем специальные символы в выводе
                            display_text = display_text.replace('\\', '\\\\')
                            warnings.append(
                                f"{rel_path}:{line_no} - Возможно жёстко заданная строка: {display_text}"
                            )
                except Exception as e:
                    warnings.append(f"Ошибка при проверке {file_path}: {str(e)}")
    
    return warnings

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
    else:
        project_path = os.getcwd()
    
    print("\nПроверка текстовых строк в проекте...")
    warnings = validate_project_texts(project_path)
    if warnings:
        print("\nПотенциальные жёстко заданные строки:")
        for w in warnings:
            print(f"- {w}")
        print("\nРекомендуется перенести эти строки в соответствующие текстовые файлы.")
    else:
        print("Жёстко заданных строк не обнаружено.")

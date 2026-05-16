import re
from typing import Dict, Any

from app.logger import get_logger

logger = get_logger("app.generator")


def parse_ddl(sql_text: str) -> Dict[str, Any]:
    """Извлекает таблицы и столбцы из SQL-скрипта"""
    # Удаляем комментарии между /* ... */ и однострочные --
    sql = re.sub(r'/\*.*?\*/', '', sql_text, flags=re.DOTALL)
    sql = re.sub(r'--.*?$', '', sql, flags=re.MULTILINE)

    # Ищем все блоки CREATE TABLE ... (
    pattern = re.compile(
        r'CREATE\s+TABLE\s+'
        r'(?:public\.)?(\w+)\s*\(',  # имя таблицы
        re.IGNORECASE
    )

    # Находим все совпадения
    tables = []
    for match in pattern.finditer(sql):
        table_name = match.group(1)
        # Ищем закрывающую скобку блока CREATE TABLE (с учётом вложенных скобок)
        start = match.end()
        depth = 1
        i = start
        while i < len(sql) and depth > 0:
            if sql[i] == '(':
                depth += 1
            elif sql[i] == ')':
                depth -= 1
            i += 1
        block = sql[start:i-1]

        # Извлекаем имена столбцов: первое слово в строке до пробела/запятой
        columns = []
        for line in block.split('\n'):
            line = line.strip()
            if not line or line.startswith('CONSTRAINT') or line.startswith('PRIMARY'):
                continue
            # Убираем "NOT NULL", "DEFAULT ..." и т.п., берем первое слово как имя колонки
            col_match = re.match(r'"?(\w+)"?\s+', line)
            if col_match:
                col_name = col_match.group(1)
                if col_name.lower() not in ('constraint', 'primary', 'foreign', 'unique'):
                    columns.append(col_name)

        tables.append({"name": table_name, "columns": columns})

    logger.debug("parse_ddl | tables_found=%d", len(tables))
    return {"tables": tables}

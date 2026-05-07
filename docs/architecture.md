# Архитектура

Система мультиагентной проверки SQL запроса состоит из следующих агентов:

- Fixer
- Generator
- Judge

## Generator

* Преобразует NL-запрос пользователя в SQL (PostgreSQL диалект)
* Использует входные данные:
    * текст задачи
    * схема БД
* Не выполняет валидацию, не оценивает корректность

### Input 

```json
{
  "task": "Найти топ-10 клиентов по сумме заказов за 2025 год",
  "schema": {
    "tables": [
      {
        "name": "customers",
        "columns": ["id", "name"]
      },
      {
        "name": "orders",
        "columns": ["id", "customer_id", "amount", "created_at"]
      }
    ]
  },
  "constraints": {
    "dialect": "postgresql",
    "read_only": true
  }
}
```

### Output

```json
{
  "sql": "SELECT ..."
}
```

## Judge

* Анализирует SQL, сгенерированный Generator
* Выявляет:
    * синтаксические ошибки
    * семантические несоответствия
    * уязвимости (SQL injection, unsafe patterns)
    * performance-проблемы
* Формирует структурированный список замечаний (issues) с приоритетами и инструкциями по исправлению
* Не изменяет SQL напрямую

### Input

```json
{
  "task": "Найти топ-10 клиентов по сумме заказов за 2025 год",
  "schema": {
    "tables": [...]
  },
  "sql": "SELECT ..."
}
```

### Output

- risk_score - чем больше тем хуже
- status - enum(REJECTED, APPROVED)
- severity - enum(LOW, MEDIUM, HIGH)
- type - enum(SEMANTIC, SECURITY, SYNTAX, PERFORMANCE, POLICY, SCHEMA)

```json
{
  "status": "REJECTED",
  "risk_score": 4,
  "issues": [
    {
      "type": "SEMANTIC",
      "severity": "HIGH",
      "message": "Нет фильтра по году 2025",
      "fix_instruction": "Добавить WHERE created_at BETWEEN '2025-01-01' AND '2025-12-31'"
    }
  ]
}
```

## Fixer

* Получает SQL + список замечаний от Judge
* Вносит точечные исправления
* Сохраняет исходный intent запроса
* Возвращает исправленную версию SQL
* Не выполняет самостоятельный анализ

### Input

```json
{
  "sql": "SELECT ...",
  "issues": [
    {
      "type": "SEMANTIC",
      "message": "Нет фильтра по году 2025",
      "fix_instruction": "Добавить WHERE created_at BETWEEN '2025-01-01' AND '2025-12-31'"
    }
  ],
  "schema": {
    "tables": [...]
  }
}
```

### Output

```json
{
  "sql": "SELECT ... WHERE created_at BETWEEN '2025-01-01' AND '2025-12-31'"
}
```
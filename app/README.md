# app

Код приложения: FastAPI-сервер и CLI для запуска агентного пайплайна генерации безопасного SQL.

## Структура

```
app/
├── api/            # FastAPI маршруты
├── fixer/          # агент-фиксер SQL
├── generator/      # агент-генератор SQL
├── judge/          # агент-судья (проверка безопасности)
├── models/         # Pydantic-схемы и состояние графа
├── orchestrator/   # LangGraph граф и раннер
├── config.py       # конфигурация через .env
├── logger.py       # настройка логирования
└── main.py         # точка входа CLI
```

## Переменные окружения

Создайте `.env` в корне проекта:

```dotenv
OPEN_ROUTER_API_KEY=sk-or-v1-...   # API-ключ OpenRouter (обязательно)
MODEL_NAME=openai/gpt-4o-mini      # модель в формате provider/model (обязательно)
```

## Запуск локально

### 1. CLI

```sh
python -m app.main generate "показать всех пользователей старше 18 лет"
```

Результат выводится в stdout: сгенерированный SQL-запрос, флаг `approved` и число итераций.

### 2. Uvicorn (HTTP API)

```sh
uvicorn app.api.routes:app --host 0.0.0.0 --port 8000 --reload
```

После запуска доступны:

- `POST /generate` — сгенерировать SQL из текста задачи

  ```json
  // запрос
  { "task": "показать всех пользователей старше 18 лет" }

  // ответ
  { "sql": "SELECT ...", "approved": true, "iterations_used": 1 }
  ```

- `GET /docs` — интерактивная документация (Swagger UI)

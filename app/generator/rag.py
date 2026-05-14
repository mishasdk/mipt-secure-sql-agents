import re
import json
import hashlib
import numpy as np
from openai import OpenAI
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.config import get_config
from app.generator.schema_loader import parse_ddl

# Глобальная переменная для кэширования полной схемы БД (синглтон)
_full_schema = None
# Глобальная переменная для хранения единственного экземпляра ретривера (синглтон)
_retriever = None


class TableRetriever:
    """Класс для поиска релевантных таблиц по текстовому запросу с использованием эмбеддингов."""

    def __init__(
        self,
        ddl_path: Optional[Path] = None,
        ddl_text: Optional[str] = None,
        embedding_model: Optional[str] = None,
        cache_dir: Optional[Path] = None
    ):
        # Получаем конфигурацию приложения (содержит API-ключ OpenRouter)
        config = get_config()
        # Создаём OpenAI клиент с базовым URL и API-ключом из конфига
        self.client = OpenAI(
            base_url=config.openrouter_base_url,
            api_key=config.open_router_api_key,
        )
        # Сохраняем название модели для эмбеддингов (по умолчанию text-embedding-3-small)
        self.embedding_model = embedding_model

        # Если передан текст DDL напрямую — используем его
        if ddl_text is not None:
            self.sql_text = ddl_text
        # Иначе если передан путь к файлу — читаем файл
        elif ddl_path is not None:
            self.sql_text = ddl_path.read_text(encoding="utf-8")
        # Иначе выбрасываем ошибку — нужен либо файл, либо текст
        else:
            raise ValueError("Нужен либо файл, либо текст со схемой БД")

        # Извлекаем из SQL все таблицы с их колонками и описаниями
        self.tables_data = self._extract_tables_with_descriptions(
            self.sql_text)
        # Сохраняем список имён таблиц для быстрого доступа
        self.table_names = [t["name"] for t in self.tables_data]
        # Сохраняем текстовые описания таблиц (используются для эмбеддингов)
        self.descriptions = [t["description"] for t in self.tables_data]

        # Директория для кэша
        if cache_dir is None and ddl_path is not None:
            cache_dir = ddl_path.parent / ".embeddings_cache"
        elif cache_dir is None:
            cache_dir = Path.cwd() / ".embeddings_cache"
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)

        # Уникальный ключ кэша на основе содержимого DDL и модели эмбеддинга
        self._cache_key = self._compute_cache_key()

        # Пытаемся загрузить эмбеддинги с диска
        self._embeddings = self._load_embeddings_from_cache()
        # Кэш для хранения результатов поиска по нормализованным запросам
        self._cache = {}    # кэш результатов retrieve

    def _compute_cache_key(self) -> str:
        """Вычисляет хеш от содержимого DDL и названия модели."""
        content_hash = hashlib.md5(self.sql_text.encode('utf-8')).hexdigest()
        combined = f"{content_hash}_{self.embedding_model}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

    def _get_embeddings_file_path(self) -> Path:
        return self.cache_dir / f"embeddings_{self._cache_key}.npy"

    def _get_metadata_file_path(self) -> Path:
        return self.cache_dir / f"metadata_{self._cache_key}.json"

    def _save_embeddings_to_cache(self):
        """Сохраняет эмбеддинги и метаданные на диск."""
        if self._embeddings is None:
            return
        np.save(self._get_embeddings_file_path(), self._embeddings)
        metadata = {
            "table_names": self.table_names,
            "descriptions": self.descriptions,
            "embedding_model": self.embedding_model,
            "embedding_dim": self._embeddings.shape[1]
        }
        with open(self._get_metadata_file_path(), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def _load_embeddings_from_cache(self) -> Optional[np.ndarray]:
        """Загружает эмбеддинги с диска, если они существуют и валидны."""
        emb_file = self._get_embeddings_file_path()
        meta_file = self._get_metadata_file_path()
        if not emb_file.exists() or not meta_file.exists():
            return None
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            # Проверяем, что модель не изменилась
            if metadata.get("embedding_model") != self.embedding_model:
                return None
            # Проверяем количество таблиц (на случай изменения DDL)
            if len(metadata.get("table_names", [])) != len(self.table_names):
                return None
            embeddings = np.load(emb_file)
            return embeddings
        except Exception:
            return None

    def _extract_tables_with_descriptions(self, sql: str) -> List[Dict[str, Any]]:
        # Используем существующий парсер для получения списка таблиц и колонок
        schema = parse_ddl(sql)
        # Извлекаем таблицы (каждая таблица — словарь с ключами name и columns)
        tables = schema["tables"]

        # Регулярное выражение для поиска COMMENT ON TABLE в SQL-скрипте
        comment_pattern = re.compile(
            r"COMMENT\s+ON\s+TABLE\s+(?:public\.)?(\w+)\s+IS\s+'(.+?)';",
            re.IGNORECASE | re.DOTALL
        )
        # Словарь для хранения комментариев к таблицам {имя_таблицы: комментарий}
        table_comments = {}
        # Проходим по всем найденным комментариям
        for match in comment_pattern.finditer(sql):
            table_name = match.group(1)             # Имя таблицы
            comment = match.group(2).strip()        # Текст комментария
            table_comments[table_name] = comment

        # Результирующий список таблиц с расширенной информацией
        result = []
        # Для каждой таблицы из парсера формируем описание
        for t in tables:
            name = t["name"]        # Имя таблицы
            cols = t["columns"]     # Список колонок
            comment = table_comments.get(name, "")  # Комментарий (если есть)
            # Базовое описание: перечисляем колонки
            description = f"Table {name} columns: {', '.join(cols)}."
            # Если есть комментарий — добавляем его к описанию
            if comment:
                description += f" {comment}"
            # Сохраняем информацию о таблице в виде словаря
            result.append({
                "name": name,
                "columns": cols,
                "description": description
            })
        return result

    def _compute_embeddings(self, texts: List[str]) -> np.ndarray:
        """Вычисляет эмбеддинги для списка текстов через OpenAI API."""
        emb = []
        # Для каждого текста вызываем API эмбеддингов
        for t in texts:
            resp = self.client.embeddings.create(
                input=t,
                model=self.embedding_model
            )
            # Проверка на пустой ответ
            if not resp.data:
                raise ValueError(
                    f"Модель {self.embedding_model} не вернула эмбеддинг для текста: {t[:50]}...")

            # Извлекаем вектор из ответа (первый элемент списка data)
            emb.append(resp.data[0].embedding)

        # Возвращаем как numpy-массив для удобства вычислений
        return np.array(emb)

    def _ensure_embeddings(self):
        """Ленивое вычисление эмбеддингов таблиц (выполняется только при первом запросе)."""
        if self._embeddings is None:
            # Пробуем загрузить с диска ещё раз (на случай параллельного доступа)
            self._embeddings = self._load_embeddings_from_cache()
            if self._embeddings is None:
                # Вычисляем через API
                self._embeddings = self._compute_embeddings(self.descriptions)
                # Сохраняем на диск
                self._save_embeddings_to_cache()

    def _normalize_query(self, query: str) -> str:
        """Нормализует строку запроса для использования в качестве ключа кэша."""
        # Приводим к нижнему регистру, удаляем лишние пробелы в начале/конце,
        # затем разбиваем на слова и склеиваем через один пробел
        return ' '.join(query.lower().strip().split())

    def retrieve(self, query: str, k: int = 15) -> List[Dict[str, Any]]:
        """Находит k таблиц, наиболее релевантных текстовому запросу."""
        # Нормализуем запрос для поиска в кэше
        norm_query = self._normalize_query(query)

        # Если результат уже есть в кэше — возвращаем его (экономим токены)
        if norm_query in self._cache:
            return self._cache[norm_query]

        # Вычисляем эмбеддинги таблиц, если они ещё не вычислены
        self._ensure_embeddings()
        # Вычисляем эмбеддинг запроса через OpenAI (один вызов)
        q_emb = self.client.embeddings.create(
            input=query,   # оригинальный запрос, не нормализованный
            model=self.embedding_model
        ).data[0].embedding

        # Нормы векторов таблиц для нормализации косинусного сходства
        norms = np.linalg.norm(self._embeddings, axis=1)
        # Косинусное сходство
        scores = np.dot(self._embeddings, q_emb) / \
            (norms * np.linalg.norm(q_emb))
        # Индексы таблиц, отсортированные по убыванию сходства, берём top-k
        top_idx = np.argsort(scores)[-k:][::-1]
        # Формируем результат — список словарей с информацией о таблицах
        result = [self.tables_data[i] for i in top_idx]

        # Сохраняем результат в кэш, чтобы при повторном запросе не обращаться к API
        self._cache[norm_query] = result
        return result

    def clear_cache(self):
        """Очищает кэш запросов."""
        self._cache.clear()


def get_retriever() -> TableRetriever:
    """Возвращает глобальный экземпляр TableRetriever (создаёт при первом вызове)."""
    global _retriever
    # Если ретривер ещё не создан — создаём его с реальным файлом data_model.sql
    if _retriever is None:
        # Берем путь к файлу из config
        config = get_config()
        ddl_path = Path(config.schema_ddl_path)
        if not ddl_path.is_absolute():
            # если путь относительный, считаем от корня проекта
            root = Path(__file__).resolve().parent.parent.parent
            ddl_path = root / config.schema_ddl_path
        _retriever = TableRetriever(ddl_path=ddl_path)
    return _retriever


def get_full_schema() -> dict:
    """Возвращает полную схему БД (все таблицы и колонки) с кэшированием."""
    global _full_schema
    # Если схема ещё не загружена — загружаем и парсим
    if _full_schema is None:
        config = get_config()
        ddl_path = Path(config.schema_ddl_path)
        if not ddl_path.is_absolute():
            root = Path(__file__).resolve().parent.parent.parent
            ddl_path = root / config.schema_ddl_path
        _full_schema = parse_ddl(ddl_path.read_text(encoding="utf-8"))
    return _full_schema


def format_schema_text(tables: List[Dict[str, Any]]) -> str:
    """Преобразует список таблиц в человекочитаемый текст для передачи в промпт LLM."""
    lines = []
    # Для каждой таблицы формируем строку вида "- имя_таблицы(колонка1, колонка2, ...)"
    for t in tables:
        # Берём список колонок, объединяем через запятую
        cols = ", ".join(t.get("columns", []))
        lines.append(f"- {t['name']}({cols})")

    # Склеиваем строки через перевод строки
    return "\n".join(lines)

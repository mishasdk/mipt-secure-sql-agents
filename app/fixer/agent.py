import json
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.fixer.schemas import FixerOutput
from app.models.state import GraphState
from app.prompts.fixer import FIXER_SYSTEM_PROMPT
from app.generator.rag import get_full_schema, format_schema_text, get_retriever


class FixerAgent:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm.with_structured_output(FixerOutput)
        # Ретривер будет создан лениво, только если потребуется fallback
        self.retriever = None
        # Загружаем полную схему БД (все таблицы и колонки) один раз при создании агента
        self.full_schema = get_full_schema()

    def _get_last_generator_tables(self, state: GraphState) -> list[str]:
        """Ищет в истории последнее сообщение генератора и извлекает tables_used."""
        # Перебираем сообщения в обратном порядке (от новых к старым)
        for msg in reversed(state["messages"]):
            # Нас интересуют только AIMessage, которые содержат ключ "tables_used"
            if isinstance(msg, AIMessage) and "tables_used" in msg.content:
                try:
                    # Парсим JSON-содержимое сообщения
                    data = json.loads(msg.content)
                    # Если поле tables_used присутствует, возвращаем его
                    if "tables_used" in data:
                        return data["tables_used"]
                except Exception:
                    # В случае ошибки парсинга пропускаем сообщение
                    pass
        # Если ни одного подходящего сообщения не найдено, возвращаем пустой список
        return []

    def __call__(self, state: GraphState) -> dict:
        # Определяем таблицы, которые использовал генератор
        tables_used = self._get_last_generator_tables(state)
        if not tables_used:
            # Fallback: если генератор не указал таблицы,
            # вызываем RAG-ретривер, чтобы получить релевантные таблицы по запросу пользователя.
            if self.retriever is None:
                self.retriever = get_retriever()
            # Находим исходный человеческий запрос (первое HumanMessage в истории)
            user_query = ""
            for msg in state["messages"]:
                if hasattr(msg, "type") and msg.type == "human":
                    user_query = msg.content
                    break
            # Получаем топ-8 наиболее релевантных таблиц через векторный поиск
            relevant = self.retriever.retrieve(user_query, k=8)
            tables_used = [t["name"] for t in relevant]

        # Фильтруем полную схему по этим таблицам
        filtered_tables = [
            t for t in self.full_schema["tables"]
            if t["name"] in tables_used
        ]
        # Превращаем отфильтрованную схему в текстовое описание для вставки в промпт
        schema_text = format_schema_text(filtered_tables)
        # Формируем системный промпт, подставляя схему
        system_prompt = FIXER_SYSTEM_PROMPT.format(schema_text=schema_text)

        # Собираем последний SQL и замечания судьи
        ai_messages = [msg for msg in state["messages"]
                       if isinstance(msg, AIMessage)]
        last_sql = ""
        if ai_messages:
            # последнее сообщение от ИИ
            last_ai = ai_messages[-1]
            try:
                # Парсим JSON, чтобы получить поле "sql"
                last_sql = json.loads(last_ai.content).get("sql", "")
            except Exception:
                pass

        # Получаем замечания от последнего вызова судьи
        judge_responses = state.get("judge_responses", [])
        last_judge = judge_responses[-1] if judge_responses else None
        issues_text = ""
        if last_judge and last_judge.issues:
            # Превращаем список замечаний в читаемый текст для LLM
            issues_text = "\n".join(
                f"- {i.type.value}: {i.message} (severity: {i.severity.value})\n  fix: {i.fix_instruction}"
                for i in last_judge.issues
            )

        # Формируем пользовательский запрос к фиксеру
        user_prompt = f"Текущий SQL:\n```sql\n{last_sql}\n```\nНарушения:\n{issues_text}"
        messages = [
            SystemMessage(content=system_prompt),   # содержит роль и схему
            # содержит SQL и список проблем
            HumanMessage(content=user_prompt)
        ]

        # Вызываем LLM и получаем исправленный SQL в структурированном виде
        output: FixerOutput = self.llm.invoke(messages)

        # Возвращаем обновлённое состояние графа
        return {
            # Добавляем новое сообщение от фиксера в формате JSON (содержит исправленный SQL)
            "messages": [AIMessage(content=output.model_dump_json(indent=2))],
            # Увеличиваем счётчик вызовов LLM на 1
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

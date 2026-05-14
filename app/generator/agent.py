from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.generator.schemas import GeneratorOutput
from app.models.state import GraphState
from app.prompts.generator import GENERATOR_SYSTEM_PROMPT
from app.generator.rag import get_retriever, format_schema_text


class GeneratorAgent:
    def __init__(self, llm: ChatOpenAI):
        # Сохраняем переданную LLM, оборачивая её в .with_structured_output,
        # чтобы ответ LLM автоматически парсился в объект GeneratorOutput (с проверкой типов)
        self.llm = llm.with_structured_output(GeneratorOutput)
        # Получаем экземпляр ретривера (один на всё приложение), который умеет выбирать релевантные таблицы по запросу
        self.retriever = get_retriever()          # инициализация один раз

    def __call__(self, state: GraphState) -> dict:
        # Извлекаем текст пользовательского запроса из состояния графа.
        # Состояние хранит список сообщений; ищем среди них сообщение типа "human".
        user_query = ""
        for msg in state["messages"]:
            if hasattr(msg, "type") and msg.type == "human":
                user_query = msg.content
                break

        # Вызываем ретривер, передавая ему текст запроса и количество таблиц, которые нужно вернуть (k=8).
        # Ретривер вычисляет эмбеддинги (с использованием OpenAI или кэша) и возвращает список словарей,
        # каждый словарь содержит имя таблицы, список колонок и текстовое описание.
        relevant_tables = self.retriever.retrieve(user_query, k=8)

        # Форматируем полученный список таблиц в читаемый текст, который будет подставлен в системный промпт.
        # Формат: каждая таблица на новой строке с перечислением колонок, например: "- users(id, name, email)"
        schema_text = format_schema_text(relevant_tables)
        # Подставляем сформированное описание схемы в шаблон системного промпта.
        system_prompt = GENERATOR_SYSTEM_PROMPT.format(schema_text=schema_text)

        # Собираем список сообщений для LLM: сначала системный промпт, затем все сообщения из состояния (история диалога).
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        # Вызываем LLM с этим списком; результат автоматически преобразуется в объект GeneratorOutput.
        output: GeneratorOutput = self.llm.invoke(messages)

        # Возвращаем обновлённое состояние графа:
        # - добавляем в список messages новое сообщение от AI, содержащее JSON с сгенерированным SQL и использованными таблицами.
        # - model_dump_json(indent=2) делает JSON отформатированным для читаемости.
        # - Увеличиваем счётчик llm_calls на 1 (для мониторинга числа вызовов LLM).
        return {
            "messages": [AIMessage(content=output.model_dump_json(indent=2))],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

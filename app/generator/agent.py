from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.generator.schemas import GeneratorOutput
from app.models.state import GraphState

GENERATOR_PROMPT = """You are a PostgreSQL generator AI agent.
Given a task description and database schema, generate a valid PostgreSQL query.
Return only the SQL query with no additional explanation.
Constraints:
- Use only the tables and columns provided in the schema
- Never use SELECT *
- Always include a WHERE clause when filtering
- Only generate read-only queries (SELECT)"""


class GeneratorAgent:
    def __init__(self, llm: ChatOpenAI, prompt: str = GENERATOR_PROMPT):
        self.llm = llm.with_structured_output(GeneratorOutput)
        self.prompt = prompt

    def __call__(self, state: GraphState) -> dict:
        messages = [SystemMessage(content=self.prompt)] + state["messages"]
        output: GeneratorOutput = self.llm.invoke(messages)
        return {
            "messages": [AIMessage(content=output.model_dump_json(indent=2))],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

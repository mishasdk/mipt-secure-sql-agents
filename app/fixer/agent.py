from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.fixer.schemas import FixerOutput
from app.models.state import GraphState

FIXER_PROMPT = """You are a PostgreSQL fixer AI agent.
You will receive a SQL query along with a list of issues found by the security auditor.
Apply targeted fixes to resolve each issue while preserving the original query intent.
Rules:
- Only modify parts of the query that have issues
- Do not introduce new logic beyond what is needed to fix the reported issues
- Return only the corrected SQL query"""


class FixerAgent:
    def __init__(self, llm: ChatOpenAI, prompt: str = FIXER_PROMPT):
        self.llm = llm.with_structured_output(FixerOutput)
        self.prompt = prompt

    def __call__(self, state: GraphState) -> dict:
        messages = [SystemMessage(content=self.prompt)] + state["messages"]
        output: FixerOutput = self.llm.invoke(messages)
        return {
            "messages": [AIMessage(content=output.model_dump_json(indent=2))],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }

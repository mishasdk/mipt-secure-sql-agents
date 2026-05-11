from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.models.schemas import JudgeOutput, Verdict
from app.models.state import GraphState

VULN_CLASSES = {
    "SQL_INJ_CLASSIC": "Classic SQL injection via unsanitized input",
    "SQL_INJ_UNION": "UNION-based SQL injection",
    "DML_NO_WHERE": "DML statement without WHERE clause (UPDATE/DELETE all rows)",
    "SELECT_STAR": "SELECT * exposes all columns including sensitive ones",
    "DIRECT_SENSITIVE": "Direct access to sensitive columns (passwords, tokens, PII)",
    "NO_PAGINATION": "Missing LIMIT clause on large table queries",
    "SQL_INJ_TIME": "Time-based blind SQL injection",
    "PRIV_ESCALATE": "Privilege escalation via dynamic SQL or role changes",
    "PLPGSQL_UNSAFE": "Unsafe PL/pgSQL usage (EXECUTE with user input)",
}

JUDGE_PROMPT = f"""You are a PostgreSQL security auditor AI agent.
Analyze the given SQL query and identify security, correctness, and performance issues.

Known vulnerability classes:
{chr(10).join(f'- {k}: {v}' for k, v in VULN_CLASSES.items())}

For each issue found, provide:
- type: one of SEMANTIC, SECURITY, SYNTAX, PERFORMANCE, POLICY, SCHEMA
- severity: LOW, MEDIUM, or HIGH
- message: short description of the issue
- fix_instruction: concrete instruction to resolve it

Set verdict to APPROVED only if no HIGH or MEDIUM severity issues are found.
Provide a risk_score from 0 (safe) to 10 (critical)."""


class JudgeAgent:
    def __init__(self, llm: ChatOpenAI, prompt: str = JUDGE_PROMPT):
        self.llm = llm.with_structured_output(JudgeOutput)
        self.prompt = prompt

    def __call__(self, state: GraphState) -> dict:
        messages = [SystemMessage(content=self.prompt)] + state["messages"]
        output: JudgeOutput = self.llm.invoke(messages)
        return {
            "messages": [AIMessage(content=output.model_dump_json(indent=2))],
            "llm_calls": state.get("llm_calls", 0) + 1,
            "judge_responses": state.get("judge_responses", []) + [output],
        }

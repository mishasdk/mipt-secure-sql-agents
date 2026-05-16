import time

from langchain_core.messages import AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.judge.ast_checker import run_ast_checks, ASTIssue
from app.judge.rules import load_policy, SecurityPolicy
from app.models.schemas import (
    FoundIssue, JudgeOutput, Verdict,
    IssueType, Severity
)
from app.models.state import GraphState
from app.logger import get_logger

logger = get_logger("app.judge")

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

def ast_issue_to_found(issue: ASTIssue) -> FoundIssue:
    return FoundIssue(
        type=IssueType(issue.type),
        severity=Severity(issue.severity),
        message=issue.message,
        fix_instruction=issue.fix_instruction,
    )


class JudgeAgent:
    def __init__(
        self,
        llm: ChatOpenAI,
        policy: SecurityPolicy | None = None,
        # prompt: str = JUDGE_PROMPT
    ):
        self.llm = llm.with_structured_output(JudgeOutput)
        # self.prompt = prompt
        self.policy = policy or load_policy()

    def __call__(self, state: GraphState) -> dict:
        # messages = [SystemMessage(content=self.prompt)] + state["messages"]
        # output: JudgeOutput = self.llm.invoke(messages)
        sql = self._extract_sql(state)
        logger.info("JudgeAgent called | sql=%r", sql[:80])

        allowlist = set(self.policy.allowlist or [])
        logger.info("tool=ast_checker | action=invoke | sql_len=%d", len(sql))
        t0 = time.perf_counter()
        issues = run_ast_checks(sql, allowlist=allowlist)
        logger.info(
            "tool=ast_checker | elapsed=%.3fs | issues=%d | rules=%s",
            time.perf_counter() - t0,
            len(issues),
            [i.rule_id for i in issues],
        )

        if not issues:
            verdict = Verdict.APPROVED
            risk_score = 0.0
        else:
            max_sev = max(
                issues,
                key=lambda i: {"LOW": 1, "MEDIUM": 5, "HIGH": 9}[i.severity],
            )
            risk_score = {"LOW": 2.0, "MEDIUM": 5.0, "HIGH": 9.0}[max_sev.severity]
            verdict = Verdict.APPROVED if risk_score < 5.0 else Verdict.REJECTED

        logger.info("JudgeAgent done | verdict=%s | risk_score=%.1f", verdict.value, risk_score)

        output = JudgeOutput(
            verdict=verdict,
            risk_score=risk_score,
            issues=[ast_issue_to_found(i) for i in issues],
        )

        return {
            "messages": [AIMessage(content=output.model_dump_json(indent=2))],
            "llm_calls": state.get("llm_calls", 0),
            "judge_responses": state.get("judge_responses", []) + [output],
        }

    @staticmethod
    def _extract_sql(state: GraphState) -> str:
        import json
        for msg in reversed(state["messages"]):
            if hasattr(msg, "content"):
                try:
                    data = json.loads(msg.content)
                    if "sql" in data:
                        return data["sql"]
                except (json.JSONDecodeError, TypeError):
                    pass
        return ""
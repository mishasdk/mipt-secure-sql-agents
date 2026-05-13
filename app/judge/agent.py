from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from app.judge.ast_checker import run_ast_checks, ASTIssue
from app.judge.rules import load_policy, SecurityPolicy
from app.models.schemas import (
    FoundIssue, JudgeOutput, Verdict,
    IssueType, Severity
)
from app.models.state import GraphState


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
    ):
        self.llm = llm.with_structured_output(JudgeOutput)
        self.policy = policy or load_policy()

    def __call__(self, state: GraphState) -> dict:
        sql = self._extract_sql(state)
        allowlist = set(self.policy.allowlist or [])
        issues = run_ast_checks(sql, allowlist=allowlist)

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
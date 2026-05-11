from langgraph.graph import END

from app.models.schemas import Verdict
from app.models.state import GraphState
from app.config import get_config


def start_iteration(state: GraphState) -> dict:
    iteration = state.get("audit_iteration")
    current = 0 if iteration is None else iteration + 1
    return {"audit_iteration": current}


def check_termination(state: GraphState) -> str:
    judge_responses = state.get("judge_responses", [])
    if not judge_responses:
        return END

    last = judge_responses[-1]
    if last.verdict == Verdict.APPROVED:
        return END

    if state.get("audit_iteration", 0) >= get_config().max_iterations:
        return END

    return "repeat"

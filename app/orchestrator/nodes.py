from langgraph.graph import END

from app.models.schemas import Verdict
from app.models.state import GraphState
from app.config import get_config
from app.logger import get_logger

logger = get_logger("app.orchestrator")


def start_iteration(state: GraphState) -> dict:
    iteration = state.get("audit_iteration")
    current = 0 if iteration is None else iteration + 1
    logger.info("iteration=%d started", current)
    return {"audit_iteration": current}


def check_termination(state: GraphState) -> str:
    judge_responses = state.get("judge_responses", [])
    iteration = state.get("audit_iteration", 0)

    if not judge_responses:
        logger.info("check_termination → END | reason=no_judge_responses")
        return END

    last = judge_responses[-1]
    if last.verdict == Verdict.APPROVED:
        logger.info("check_termination → END | verdict=APPROVED | iteration=%d", iteration)
        return END

    if iteration >= get_config().max_iterations:
        logger.info("check_termination → END | reason=max_iterations | iteration=%d", iteration)
        return END

    logger.info("check_termination → repeat | verdict=%s | iteration=%d", last.verdict.value, iteration)
    return "repeat"

import json
import time

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.models.schemas import Verdict
from app.models.state import IterationLog, PipelineResult
from app.orchestrator.graph import build_graph
from app.logger import get_logger

logger = get_logger("app.orchestrator.runner")


def run(query: str, llm: ChatOpenAI | None = None) -> PipelineResult:
    logger.info("Pipeline started | query=%r", query[:120])
    t0 = time.perf_counter()
    state = build_graph(llm).invoke({"messages": [HumanMessage(content=query)]})

    judge_responses = state.get("judge_responses", [])
    ai_messages = [msg for msg in state["messages"] if isinstance(msg, AIMessage)]
    sql_messages = ai_messages[::2]

    logs = [
        IterationLog(
            iteration=idx,
            sql_query=json.loads(sql_msg.content)["sql"],
            judge_output=judge_output,
        )
        for idx, (sql_msg, judge_output) in enumerate(zip(sql_messages, judge_responses))
    ]

    last_judge = judge_responses[-1] if judge_responses else None
    result = PipelineResult(
        final_sql=json.loads(sql_messages[-1].content)["sql"] if sql_messages else "",
        approved=last_judge.verdict == Verdict.APPROVED if last_judge else False,
        iterations_used=state.get("audit_iteration", 0),
        iteration_logs=logs,
    )

    logger.info(
        "Pipeline finished | elapsed=%.2fs | iterations=%d | llm_calls=%d | approved=%s | sql=%r",
        time.perf_counter() - t0,
        result.iterations_used,
        state.get("llm_calls", 0),
        result.approved,
        result.final_sql[:80],
    )
    return result

import json

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI

from app.models.schemas import Verdict
from app.models.state import IterationLog, PipelineResult
from app.orchestrator.graph import build_graph


def run(query: str, llm: ChatOpenAI | None = None) -> PipelineResult:
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
    return PipelineResult(
        final_sql=json.loads(sql_messages[-1].content)["sql"] if sql_messages else "",
        approved=last_judge.verdict == Verdict.APPROVED if last_judge else False,
        iterations_used=state.get("audit_iteration", 0),
        iteration_logs=logs,
    )

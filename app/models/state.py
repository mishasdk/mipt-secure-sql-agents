from datetime import datetime
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from typing_extensions import TypedDict

from app.models.schemas import JudgeOutput


class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    judge_responses: list[JudgeOutput]
    llm_calls: int
    audit_iteration: int


class IterationLog(BaseModel):
    iteration: int
    sql_query: str
    judge_output: JudgeOutput
    timestamp: datetime = datetime.now()


class PipelineResult(BaseModel):
    final_sql: str
    approved: bool
    iterations_used: int
    iteration_logs: list[IterationLog]

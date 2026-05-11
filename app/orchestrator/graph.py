from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from app.config import get_config
from app.fixer.agent import FixerAgent
from app.generator.agent import GeneratorAgent
from app.judge.agent import JudgeAgent
from app.models.state import GraphState
from app.orchestrator.nodes import check_termination, start_iteration


def build_graph(llm: ChatOpenAI | None = None):
    if llm is None:
        config = get_config()
        llm = ChatOpenAI(
            base_url=config.openrouter_base_url,
            api_key=config.open_router_api_key,
            model=config.model_name,
        )

    generator = GeneratorAgent(llm)
    judge = JudgeAgent(llm)
    fixer = FixerAgent(llm)

    graph = StateGraph(GraphState)

    graph.add_node("generator", generator)
    graph.add_node("start_iteration", start_iteration)
    graph.add_node("judge", judge)
    graph.add_node("fixer", fixer)

    graph.add_edge(START, "generator")
    graph.add_edge("generator", "start_iteration")
    graph.add_edge("start_iteration", "judge")
    graph.add_conditional_edges(
        "judge",
        check_termination,
        {"repeat": "fixer", END: END},
    )
    graph.add_edge("fixer", "start_iteration")

    return graph.compile()

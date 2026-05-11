# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mipt-secure-sql-agents** is a multi-agent system that generates PostgreSQL queries from natural language, validates them for security vulnerabilities, and iteratively fixes issues until approval. It's built as an MVP for MIPT's practical course project.

The system implements a **RAG-style agentic loop**: Natural Language → SQL Generation → Security Validation → Iterative Fixing.

## Architecture

The system is organized into four autonomous agents orchestrated by LangGraph:

1. **Generator** (`app/generator/agent.py`)
   - Converts natural language user requests into PostgreSQL (read-only SELECT queries)
   - Uses OpenRouter LLM with structured output (Pydantic model)
   - Input: raw user task + DB schema
   - Output: JSON with `sql` and `tables_used`
   - No validation performed—purely generative

2. **Judge** (`app/judge/agent.py`)
   - Security auditor that analyzes generated SQL
   - Detects: syntax errors, semantic issues, SQL injection vectors, unsafe patterns, performance problems, policy violations, schema mismatches
   - Returns structured `JudgeOutput` with verdict (APPROVED/REJECTED), risk_score (0-10), and list of issues
   - Approves only if no HIGH or MEDIUM severity issues exist
   - Known vulnerability classes tracked in prompt (SQL injection variants, SELECT *, missing WHERE clauses, privilege escalation, unsafe PL/pgSQL, etc.)

3. **Fixer** (`app/fixer/agent.py`)
   - Receives SQL + list of issues from Judge
   - Applies **targeted fixes only** to problem areas
   - Preserves original query intent—constrained prompt prevents hallucination loops
   - Returns corrected SQL

4. **Orchestrator** (`app/orchestrator/graph.py`)
   - LangGraph state machine implementing the loop: `START → Generator → Judge → (if issues: Fixer → Generator | if approved: END)`
   - State machine enforces termination: max iterations (default 3) or APPROVED verdict
   - Each iteration tracked with audit logging

### Data Flow

```
User Query (NL)
    ↓
[Generator] → SQL (JSON with metadata)
    ↓
[Judge] → Issues + Verdict
    ↓
    ├─ APPROVED → Return SQL
    │
    └─ REJECTED → [Fixer] → Modified SQL → back to Judge (loop)
```

### Key Models & State

**GraphState** (`app/models/state.py`):
- `messages`: LangChain message chain (HumanMessage → AIMessage flow)
- `judge_responses`: list of all JudgeOutput objects across iterations
- `audit_iteration`: loop counter
- `llm_calls`: total LLM invocations

**PipelineResult** (`app/models/state.py`):
- `final_sql`: approved SQL or last attempt
- `approved`: boolean verdict
- `iterations_used`: how many loops executed
- `iteration_logs`: detailed audit trail (each iteration captures SQL + judge output + timestamp)

**Verdict & Severity** (`app/models/schemas.py`):
- Verdict: `APPROVED | REJECTED`
- Severity: `LOW | MEDIUM | HIGH`
- IssueType: `SEMANTIC | SECURITY | SYNTAX | PERFORMANCE | POLICY | SCHEMA`

## Running the System

### Setup

```bash
# Create and activate venv
python3 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```

**Environment variables** (create `.env` in project root):
```dotenv
OPEN_ROUTER_API_KEY=sk-or-v1-...   # OpenRouter API key (required)
MODEL_NAME=openai/gpt-4o-mini      # Model in provider/model format (required)
```

### CLI Usage

```bash
python -m app.main generate "find all users older than 18"
```

Outputs JSON with structure:
```json
{
  "final_sql": "SELECT id, name FROM users WHERE age > 18",
  "approved": true,
  "iterations_used": 1,
  "iteration_logs": [...]
}
```

### FastAPI Server

```bash
uvicorn app.api.routes:app --host 0.0.0.0 --port 8000 --reload
```

Available endpoints:
- `POST /generate` - Accept `{"task": "..."}`, return `{"sql": "...", "approved": bool, "iterations_used": int}`
- `GET /docs` - Swagger UI interactive documentation

## Development Workflow

### Project Structure

```
app/
├── models/
│   ├── schemas.py      # Pydantic models: JudgeOutput, Verdict, FoundIssue, IssueType, Severity
│   └── state.py        # GraphState, IterationLog, PipelineResult
├── generator/
│   ├── agent.py        # GeneratorAgent class + GENERATOR_PROMPT
│   └── schemas.py      # GeneratorOutput (sql + tables_used)
├── judge/
│   ├── agent.py        # JudgeAgent class + JUDGE_PROMPT + VULN_CLASSES dict
│   └── (no schemas—uses models/schemas.py directly)
├── fixer/
│   ├── agent.py        # FixerAgent class + FIXER_PROMPT
│   └── schemas.py      # FixerOutput (sql)
├── orchestrator/
│   ├── graph.py        # build_graph() - constructs LangGraph StateGraph
│   ├── nodes.py        # start_iteration(), check_termination() helper nodes
│   └── runner.py       # run() - invokes graph and structures results
├── api/
│   └── routes.py       # FastAPI app + /generate endpoint
├── config.py           # Config class (Pydantic) + get_config() with validation
├── logger.py           # setup_logging() + get_logger()
└── main.py             # CLI argument parser + entry point
```

### Adding a New Agent

1. Create `app/new_agent/agent.py` with class inheriting callable pattern (see GeneratorAgent/JudgeAgent/FixerAgent)
2. Define structured Pydantic output model in `app/new_agent/schemas.py`
3. Create prompt string as module constant
4. In orchestrator `graph.py`, import agent, add node with `graph.add_node("name", agent_instance)`, define edges
5. Update GraphState in `models/state.py` if you need to track new state fields

### Modifying Prompts & Rules

All agent prompts are defined as module-level strings:
- `GENERATOR_PROMPT` in `app/generator/agent.py`
- `JUDGE_PROMPT` in `app/judge/agent.py` (also references `VULN_CLASSES` dict)
- `FIXER_PROMPT` in `app/fixer/agent.py`

Judge vulnerability classes can be extended by adding entries to `VULN_CLASSES` dict.

### Configuration

All settings in `app/config.py` (Config class):
- `max_iterations`: termination condition (default 3)
- `risk_threshold`: unused currently, reserved for future severity-based early exit
- `model_name`: provider/model format validated on load
- `open_router_api_key`: validated as non-empty

Customize via environment variables or update defaults in `Config` class.

## Testing & Debugging

### Manual Testing

```bash
# CLI test
python -m app.main generate "select top 10 customers by order amount"

# FastAPI - start server, then:
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"task": "show all users"}'
```

### Logging

Logger initialized in `app/logger.py`:
- Output to stderr with timestamps
- Configure level via `setup_logging(level=logging.DEBUG)`
- FastAPI routes use logger for request timing

Jupyter notebooks in `notebook/` contain research & debugging scripts:
- `LLM_Intelligence.ipynb` - LLM API exploration
- `orchestrator.ipynb` - graph execution walkthrough
- `llm_api.ipynb` - OpenRouter client testing

### Debugging Agent Flow

`iteration_logs` in PipelineResult contains full audit trail:
```python
result = run(query)
for log in result.iteration_logs:
    print(f"Iteration {log.iteration}:")
    print(f"  SQL: {log.sql_query}")
    print(f"  Issues: {log.judge_output.issues}")
    print(f"  Verdict: {log.judge_output.verdict}")
```

## Important Design Constraints

1. **Fixer Prompt**: Deliberately narrow scope to prevent hallucination loops. Fixer only touches reported issues, never rewrites entire query.

2. **Generator Output**: Always JSON with explicit `tables_used` field to improve traceability and reduce false positives in Judge.

3. **Judge Verdict Logic**: `APPROVED` only if *no HIGH or MEDIUM issues*. LOW severity issues are allowed (e.g., optimization suggestions).

4. **Read-Only Enforcement**: Generator constrained to SELECT only (no INSERT/UPDATE/DELETE). Config allows allowlisting specific tables in future.

5. **LangGraph Message Chain**: GraphState uses LangChain's `add_messages` reducer to maintain full conversation history. Each agent appends AIMessage; this enables multi-turn debugging but can grow memory usage.

## Dependencies & LLM Integration

Key packages:
- `fastapi` - REST API framework
- `uvicorn` - ASGI server
- `langchain-openai` - ChatOpenAI client
- `langgraph` - state machine orchestration
- `pydantic` - schema validation & structured output
- `python-dotenv` - environment loading

LLM Integration:
- **Provider**: OpenRouter (abstraction over multiple LLM providers)
- **Model Format**: `provider/model` (e.g., `openai/gpt-4o-mini`, `anthropic/claude-3-sonnet`)
- **Structured Output**: All agents use `.with_structured_output(PydanticModel)` to enforce JSON schema compliance

## Branches & Workflow

Current branches:
- `master` - stable main
- `mishasdk/develop-orchestrator` - active development (graph & orchestration)
- `mishasdk/llm-api` - LLM integration experiments
- `sonia/backend-mvp` - FastAPI backend work
- `mishasdk/llm-graph` - LangGraph explorations

Team assignments (from project vision):
- Orchestrator: Misha
- LLM Intelligence (Generator + Fixer prompts): Anton
- Security & Correctness (Judge + validation): Dima
- Backend, Client, QA, Logging, Rules: Sonia


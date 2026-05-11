import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.logger import get_logger, setup_logging
from app.orchestrator.runner import run


_startup_time = time.time()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging(configure_uvicorn=True)
    logger.info("server starting up")
    yield
    logger.info("server shutting down")


app = FastAPI(title="Secure SQL Agents", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - t0) * 1000
    logger.info("%s %s %d %.1fms", request.method, request.url.path, response.status_code, ms)
    return response


@app.get("/health", summary="Health check")
def health():
    return {"status": "ok", "uptime_seconds": round(time.time() - _startup_time)}


class GenerateRequest(BaseModel):
    task: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"task": "Find all users who made a purchase in the last 30 days"}
            ]
        }
    }


class GenerateResponse(BaseModel):
    sql: str
    approved: bool
    iterations_used: int


@app.post(
    "/generate",
    response_model=GenerateResponse,
    summary="Generate SQL from natural language"
)
def generate_sql(request: GenerateRequest):
    result = run(request.task)
    return GenerateResponse(
        sql=result.final_sql,
        approved=result.approved,
        iterations_used=result.iterations_used,
    )

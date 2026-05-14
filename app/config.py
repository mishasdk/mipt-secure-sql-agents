import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, field_validator

load_dotenv()


class Config(BaseModel):
    open_router_api_key: str = os.getenv("OPEN_ROUTER_API_KEY")
    model_name: str = os.getenv("MODEL_NAME")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    max_iterations: int = 3
    risk_threshold: float = 4.0

    # Модель ембеддингов и путь к схеме БД
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "perplexity/pplx-embed-v1-4b")
    schema_ddl_path: str = os.getenv("SCHEMA_DDL_PATH", "app/data_model.sql")

    @field_validator("open_router_api_key")
    @classmethod
    def require_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("OPEN_ROUTER_API_KEY is not set")
        return v

    @field_validator("model_name")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if not v:
            raise ValueError("MODEL_NAME cannot be empty")
        if "/" not in v:
            raise ValueError(
                "MODEL_NAME must be in 'provider/model' format, e.g. 'openai/gpt-4o-mini'")
        return v


@lru_cache
def get_config() -> Config:
    return Config()

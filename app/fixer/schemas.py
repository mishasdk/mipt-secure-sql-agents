from pydantic import BaseModel, Field


class FixerOutput(BaseModel):
    sql: str = Field(description="Fixed SQL query")

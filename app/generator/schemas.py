from pydantic import BaseModel, Field


class TableSchema(BaseModel):
    name: str
    columns: list[str]


class DBSchema(BaseModel):
    tables: list[TableSchema]


class GeneratorOutput(BaseModel):
    sql: str = Field(description="Generated SQL query")
    tables_used: list[str] = Field(default_factory=list, description="List of table names used in the query")

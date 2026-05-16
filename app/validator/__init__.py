from dataclasses import dataclass, field


@dataclass
class ValidatorWarning:
    type: str
    severity: str
    message: str
    detail: str = ""


@dataclass
class ValidatorOutput:
    valid: bool = True
    explain_plan: str = ""
    warnings: list[ValidatorWarning] = field(default_factory=list)


def validate_sql(
    sql: str,
    schema: dict | None = None,
    dsn: str | None = None,
) -> ValidatorOutput:
    return ValidatorOutput(valid=True)
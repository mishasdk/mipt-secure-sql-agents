from enum import Enum

from pydantic import BaseModel, Field


class IssueType(str, Enum):
    SEMANTIC = "SEMANTIC"
    SECURITY = "SECURITY"
    SYNTAX = "SYNTAX"
    PERFORMANCE = "PERFORMANCE"
    POLICY = "POLICY"
    SCHEMA = "SCHEMA"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Verdict(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class FoundIssue(BaseModel):
    type: IssueType
    severity: Severity
    message: str = Field(description="Short human readable issue description")
    fix_instruction: str = Field(description="Direct instruction of what needs to be resolved")


class JudgeOutput(BaseModel):
    verdict: Verdict
    risk_score: float = Field(ge=0, le=10, description="Overall risk score, higher is worse")
    issues: list[FoundIssue] = Field(default_factory=list)

from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class ASTRule(BaseModel):
    id: str
    name: str
    description: str
    severity: str          # LOW | MEDIUM | HIGH
    type: str              # SECURITY | PERFORMANCE | POLICY | SCHEMA | SYNTAX
    check: str             # "ast" | "llm"
    ast_check: Optional[dict] = None
    llm_prompt: Optional[str] = None


class SecurityPolicy(BaseModel):
    rules: list[ASTRule]
    allowlist: Optional[list[str]] = None


def load_policy(path: Optional[str] = None) -> SecurityPolicy:
    if path is None:
        current_dir = Path(__file__).resolve().parent
        path = current_dir / "res" / "security_rules.yaml"
    else:
        path = Path(path)

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SecurityPolicy(**raw)

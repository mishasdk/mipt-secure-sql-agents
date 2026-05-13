from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pglast
from pglast import enums, visitors


@dataclass
class IssueLocation:
    line: int
    column: int


@dataclass
class ASTIssue:
    rule_id: str
    message: str
    severity: str          # LOW | MEDIUM | HIGH
    type: str              # SECURITY | PERFORMANCE | POLICY | SCHEMA | SYNTAX
    fix_instruction: str
    location: Optional[IssueLocation] = None


class SecurityVisitor(visitors.Visitor):

    def __init__(self, allowlist: Optional[set[str]] = None):
        super().__init__()
        self.issues: list[ASTIssue] = []
        self.allowlist = allowlist or set()

    # ── R01: SELECT * ───────────────────────────────────
    def visit_A_Star(self, ancestors, node):
        loc = self._location(node)
        self.issues.append(ASTIssue(
            rule_id="R01",
            message="SELECT * exposes all columns, including sensitive ones",
            severity="MEDIUM",
            type="SECURITY",
            fix_instruction="Replace * with explicit column list",
            location=loc,
        ))

    # ── R02: DML without WHERE ──────────────────────────
    def visit_UpdateStmt(self, ancestors, node):
        self._check_dml_where(node, "UPDATE")

    def visit_DeleteStmt(self, ancestors, node):
        self._check_dml_where(node, "DELETE")

    def _check_dml_where(self, node, dml_type: str):
        if node.whereClause is None:
            loc = self._location(node)
            self.issues.append(ASTIssue(
                rule_id="R02",
                message=f"{dml_type} without WHERE clause affects ALL rows",
                severity="HIGH",
                type="SECURITY",
                fix_instruction=f"Add a WHERE clause to the {dml_type} statement",
                location=loc,
            ))

    # ── R03: Missing LIMIT ──────────────────────────────
    def visit_SelectStmt(self, ancestors, node):
        if (node.limitCount is None
                and node.op == enums.SetOperation.SETOP_NONE):
            loc = self._location(node)
            self.issues.append(ASTIssue(
                rule_id="R03",
                message="SELECT without LIMIT may return excessive rows",
                severity="LOW",
                type="PERFORMANCE",
                fix_instruction="Add a LIMIT clause (max 1000)",
                location=loc,
            ))

    # ── R04: Table allowlist check ──────────────────────
    def visit_RangeVar(self, ancestors, node):
        if self.allowlist and node.relname not in self.allowlist:
            loc = self._location(node)
            self.issues.append(ASTIssue(
                rule_id="R04",
                message=f"Table '{node.relname}' is not in the allowed list",
                severity="HIGH",
                type="POLICY",
                fix_instruction=f"Use only allowed tables: {', '.join(sorted(self.allowlist))}",
                location=loc,
            ))

    # ── Helpers ─────────────────────────────────────────
    @staticmethod
    def _location(node) -> IssueLocation:
        try:
            line = getattr(node, 'location', None)
            if line is None:
                line = 1
            return IssueLocation(line=line, column=0)
        except Exception:
            return IssueLocation(line=1, column=0)


def run_ast_checks(
    sql: str,
    allowlist: Optional[set[str]] = None,
) -> list[ASTIssue]:
    try:
        stmts = pglast.parse_sql(sql)
    except Exception as e:
        return [ASTIssue(
            rule_id="SYNTAX",
            message=f"SQL syntax error: {e}",
            severity="HIGH",
            type="SYNTAX",
            fix_instruction="Fix SQL syntax before proceeding",
        )]

    visitor = SecurityVisitor(allowlist=allowlist)
    for stmt in stmts:
        visitor(stmt)
    return visitor.issues
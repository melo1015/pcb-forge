"""Shared typed models."""
from pydantic import BaseModel, Field


class Diagnostic(BaseModel):
    code: str
    message: str
    severity: str = "error"
    source: str = "pcb-forge"
    path: str | None = None


class ValidationReport(BaseModel):
    project_path: str
    checks_run: list[str] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    passed: bool = False
    notes: list[str] = Field(default_factory=list)

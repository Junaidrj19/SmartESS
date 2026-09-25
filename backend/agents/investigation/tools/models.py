from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolError(ValueError):
    def __init__(self, tool: str, message: str):
        self.tool = tool
        super().__init__(f"[{tool}] {message}")


class ToolInput(BaseModel):
    values: List[float] = Field(description="Numerical series to analyze")
    module_id: str = ""
    signal_name: str = ""
    metadata: Dict[str, Any] = {}


class ToolResult(BaseModel):
    tool_name: str
    tool_version: str = "1.0.0"
    input_summary: Dict[str, Any] = {}
    output: Dict[str, Any] = {}
    provenance: Dict[str, Any] = {}
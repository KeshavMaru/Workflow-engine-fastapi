from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StateModel(BaseModel):
    source_code: Optional[Union[str, Dict[str, str]]] = Field(
        default=None, description="Full source code or mapping filename -> content"
    )
    functions: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, description="Extracted functions and metadata"
    )
    quality_score: Optional[float] = Field(
        default=None, description="Numeric quality score used for loop decisions"
    )
    issues: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, description="Detected issues collected by the workflow"
    )
    suggestions: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list, description="Suggested improvements produced by the workflow"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Arbitrary metadata for nodes and tools"
    )


class NodeSpec(BaseModel):
    name: str = Field(..., description="Unique node identifier")
    type: Optional[str] = Field(default="action", description="Node type hint")
    config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Configuration passed to the node"
    )


class EdgeSpec(BaseModel):
    from_node: str = Field(..., description="Source node name")
    to_node: Union[str, Dict[str, str]] = Field(
        ..., description="Destination node name or mapping condition -> destination"
    )


class GraphSpec(BaseModel):
    nodes: List[NodeSpec] = Field(..., description="List of node specifications")
    edges: List[EdgeSpec] = Field(default_factory=list, description="List of edges")
    start_node: str = Field(..., description="Entry point node name")
    max_iterations: int = Field(default=100, description="Maximum node executions per run")


class CreateGraphResponse(BaseModel):
    graph_id: str = Field(..., description="Identifier for the stored graph")


class RunRequest(BaseModel):
    graph_id: str = Field(..., description="Identifier of the graph to run")
    initial_state: Optional[StateModel] = Field(default_factory=StateModel, description="Initial shared state")


class LogEntry(BaseModel):
    step_index: int = Field(..., description="Execution step index starting at 0")
    node_name: str = Field(..., description="The node that executed")
    state_snapshot: Dict[str, Any] = Field(default_factory=dict, description="Serializable snapshot of state")
    message: Optional[str] = Field(default=None, description="Optional message for the log entry")
    error: Optional[str] = Field(default=None, description="Optional error message")


class RunInfo(BaseModel):
    run_id: str = Field(..., description="Unique run identifier")
    graph_id: str = Field(..., description="Graph identifier for this run")
    status: RunStatus = Field(..., description="Current status of the run")
    current_node: Optional[str] = Field(default=None, description="Currently executing or last executed node")
    step_count: int = Field(default=0, description="Number of executed steps so far")
    logs: List[LogEntry] = Field(default_factory=list, description="Execution log entries")
    final_state: Optional[StateModel] = Field(default=None, description="Final state when run completes")


class RunResponse(BaseModel):
    run_id: str = Field(..., description="Identifier for the run")
    final_state: Optional[StateModel] = Field(default=None, description="Final state if the run completed")
    logs: List[LogEntry] = Field(default_factory=list, description="Execution logs")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, Optional, Tuple

from app.schemas import (
    GraphSpec,
    RunInfo,
    RunStatus,
    LogEntry,
    StateModel,
)
from app.nodes_tools import NODE_FUNCTIONS, registered_tools

stored_graphs: Dict[str, GraphSpec] = {}
stored_runs: Dict[str, RunInfo] = {}
stored_run_queues: Dict[str, asyncio.Queue] = {}


class WorkflowEngine:
    def create_graph(self, graph: GraphSpec) -> str:
        graph_identifier = str(uuid.uuid4())
        stored_graphs[graph_identifier] = graph
        return graph_identifier

    def create_run(self, graph_identifier: str, initial_state: Optional[StateModel]) -> str:
        run_identifier = str(uuid.uuid4())
        run_info = RunInfo(
            run_id=run_identifier,
            graph_id=graph_identifier,
            status=RunStatus.PENDING,
            current_node=None,
            step_count=0,
            logs=[],
            final_state=None,
        )
        stored_runs[run_identifier] = run_info
        if initial_state is None:
            initial_state = StateModel()
        run_info.final_state = initial_state
        return run_identifier

    async def run_workflow(self, run_identifier: str, publish_queue: Optional[asyncio.Queue] = None) -> RunInfo:
        run_info = stored_runs[run_identifier]
        graph = stored_graphs[run_info.graph_id]
        run_info.status = RunStatus.RUNNING

        current_state = run_info.final_state or StateModel()
        current_node_name = graph.start_node
        run_info.current_node = current_node_name

        edges_map = self.build_edges_map(graph)

        for step_number in range(graph.max_iterations):
            if current_node_name not in NODE_FUNCTIONS:
                run_info.status = RunStatus.FAILED
                run_info.final_state = current_state
                if publish_queue is not None:
                    await publish_queue.put({"type": "completion", "run_info": run_info.dict()})
                break

            node_function = NODE_FUNCTIONS[current_node_name]
            node_config = self.get_node_config(graph, current_node_name)

            try:
                next_key, updated_state, message = await node_function(
                    current_state, registered_tools, node_config
                )
            except Exception as execution_error:
                log_entry = LogEntry(
                    step_index=step_number,
                    node_name=current_node_name,
                    state_snapshot=current_state.dict(),
                    message=str(execution_error),
                    error=str(execution_error),
                )
                run_info.logs.append(log_entry)
                run_info.status = RunStatus.FAILED
                run_info.final_state = current_state
                if publish_queue is not None:
                    await publish_queue.put({"type": "log", "entry": log_entry.dict()})
                    await publish_queue.put({"type": "completion", "run_info": run_info.dict()})
                break

            current_state = updated_state
            log_entry = LogEntry(
                step_index=step_number,
                node_name=current_node_name,
                state_snapshot=current_state.dict(),
                message=message,
                error=None,
            )
            run_info.logs.append(log_entry)
            run_info.step_count = step_number + 1

            if publish_queue is not None:
                await publish_queue.put({"type": "log", "entry": log_entry.dict()})

            if next_key is None:
                run_info.status = RunStatus.COMPLETED
                run_info.final_state = current_state
                if publish_queue is not None:
                    await publish_queue.put({"type": "completion", "run_info": run_info.dict()})
                break

            found, next_node_name = self.resolve_next_node(edges_map, current_node_name, next_key)
            if not found:
                run_info.status = RunStatus.FAILED
                run_info.final_state = current_state
                if publish_queue is not None:
                    await publish_queue.put({"type": "completion", "run_info": run_info.dict()})
                break

            if next_node_name is None:
                run_info.status = RunStatus.COMPLETED
                run_info.final_state = current_state
                if publish_queue is not None:
                    await publish_queue.put({"type": "completion", "run_info": run_info.dict()})
                break

            current_node_name = next_node_name
            run_info.current_node = current_node_name

        else:
            run_info.status = RunStatus.FAILED
            run_info.final_state = current_state
            if publish_queue is not None:
                await publish_queue.put({"type": "completion", "run_info": run_info.dict()})

        return run_info

    def build_edges_map(self, graph: GraphSpec) -> Dict[str, Any]:
        mapping: Dict[str, Any] = {}
        for edge in graph.edges:
            mapping[edge.from_node] = edge.to_node
        return mapping

    def get_node_config(self, graph: GraphSpec, node_name: str) -> Optional[Dict[str, Any]]:
        for node in graph.nodes:
            if node.name == node_name:
                return node.config
        return None

    def resolve_next_node(
        self, edges_map: Dict[str, Any], current_node_name: str, next_key: Optional[str]
    ) -> Tuple[bool, Optional[str]]:
        if current_node_name not in edges_map:
            return False, None

        destination = edges_map[current_node_name]

        if isinstance(destination, str):
            return True, destination

        if isinstance(destination, dict):
            if next_key in destination:
                return True, destination.get(next_key)
            return False, None

        return False, None


workflow_engine = WorkflowEngine()

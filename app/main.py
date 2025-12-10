from __future__ import annotations

import asyncio
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse

from app.schemas import GraphSpec, CreateGraphResponse, RunRequest, RunInfo
from app.engine import workflow_engine, stored_graphs, stored_runs, stored_run_queues

app = FastAPI(title="Workflow Engine")


@app.post("/graph/create", response_model=CreateGraphResponse)
def create_graph(graph_specification: GraphSpec):
    graph_identifier = workflow_engine.create_graph(graph_specification)
    return CreateGraphResponse(graph_id=graph_identifier)


@app.post("/graph/run")
async def run_graph(request: RunRequest):
    if request.graph_id not in stored_graphs:
        raise HTTPException(status_code=404, detail="Graph not found")
    run_identifier = workflow_engine.create_run(request.graph_id, request.initial_state)
    publish_queue: asyncio.Queue = asyncio.Queue()
    stored_run_queues[run_identifier] = publish_queue
    asyncio.create_task(workflow_engine.run_workflow(run_identifier, publish_queue=publish_queue))
    return JSONResponse({"run_id": run_identifier})


@app.get("/graph/state/{run_identifier}", response_model=RunInfo)
def get_run_state(run_identifier: str):
    if run_identifier not in stored_runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return stored_runs[run_identifier]


@app.websocket("/graph/ws/{run_identifier}")
async def websocket_run_stream(websocket: WebSocket, run_identifier: str):
    await websocket.accept()
    if run_identifier not in stored_run_queues:
        await websocket.close(code=1008)
        return
    publish_queue: asyncio.Queue = stored_run_queues[run_identifier]
    try:
        while True:
            message = await publish_queue.get()
            await websocket.send_json(message)
            if isinstance(message, dict) and message.get("type") == "completion":
                break
    except WebSocketDisconnect:
        return
    finally:
        if run_identifier in stored_run_queues:
            try:
                del stored_run_queues[run_identifier]
            except KeyError:
                pass

# Workflow Engine (Simplified LangGraph-Style Agent Framework)

This project implements a minimal workflow (graph) engine inspired by LangGraph.
It allows defining nodes, connecting them with edges, maintaining shared state, and running the workflow end-to-end through FastAPI APIs.
The goal is to demonstrate understanding of Python backend fundamentals: async execution, state management, API design, and clean code structure.


**Features**

**1. Minimal Workflow Engine**

* Nodes are Python async functions.
* Each node receives and updates a shared `StateModel`.
* Edges define which node executes next.
* Supports simple branching using node return values.
* Supports looping (repeat nodes until a condition is met).
* Execution log captures every step with node name, state snapshot, and message.

**2. Tool Registry**

* Simple dictionary-based tool store.
* Nodes can call reusable tools (e.g., complexity estimator, linter, suggestion generator).

**3. FastAPI Endpoints**

| Method        | Endpoint                | Description                                                 |
| ------------- | ----------------------- | ----------------------------------------------------------- |
| **POST**      | `/graph/create`         | Register a workflow graph. Returns `graph_id`.              |
| **POST**      | `/graph/run`            | Start a workflow run in the background. Returns `run_id`.   |
| **GET**       | `/graph/state/{run_id}` | Get the latest state + logs of an ongoing or completed run. |
| **WebSocket** | `/graph/ws/{run_id}`    | Real-time streaming of logs from the running workflow.      |

**4. Background Execution**

* Workflows run asynchronously using `asyncio.create_task`.
* Allows streaming logs before the run finishes.

**5. Example Workflow: Code Review Mini-Agent**

A sample workflow demonstrating all engine capabilities:

1. **extract_functions**
2. **check_complexity**
3. **detect_issues**
4. **suggest_improvements**
5. **compute_quality** (loops until `quality_score >= threshold`)

This is fully implemented using rule-based logic (no ML required).


## **Project Structure**

```
app/
│
├── main.py              # FastAPI app: REST + WebSocket endpoints
├── engine.py            # Workflow engine core: execution, routing, logging
├── schemas.py           # Pydantic models for graph, state, runs, logs
└── nodes_tools.py       # Node implementations and tool registry
```

**How to Run**

**1. Install dependencies**

```
pip install fastapi uvicorn pydantic
```
**2. Start the server**

```
uvicorn app.main:app --reload
```

Server runs at:
`http://127.0.0.1:8000`



**Example Usage**
**1. Create the workflow graph**

POST to:

```
/graph/create
```

Body:

```json
{
  "nodes": [
    {"name": "extract_functions", "type": "action", "config": {}},
    {"name": "check_complexity", "type": "action", "config": {}},
    {"name": "detect_issues", "type": "action", "config": {}},
    {"name": "suggest_improvements", "type": "action", "config": {}},
    {"name": "compute_quality", "type": "action", "config": {"threshold": 90}}
  ],
  "edges": [
    {"from_node": "extract_functions", "to_node": "check_complexity"},
    {"from_node": "check_complexity", "to_node": "detect_issues"},
    {"from_node": "detect_issues", "to_node": "suggest_improvements"},
    {"from_node": "suggest_improvements", "to_node": "compute_quality"},
    {"from_node": "compute_quality", "to_node": {"check_complexity": "check_complexity"}}
  ],
  "start_node": "extract_functions",
  "max_iterations": 20
}
```

Response:

```json
{ "graph_id": "..." }
```

**2. Start a workflow run**

POST to:

```
/graph/run
```

Body:

```json
{
  "graph_id": "YOUR_GRAPH_ID",
  "initial_state": {
    "source_code": "def add(a,b): return a+b"
  }
}
```

Response:

```json
{ "run_id": "..." }
```

**3. View run state**

```
/graph/state/{run_id}
```

Returns:

* current node
* step count
* logs
* final state (if completed)

**4. Stream logs in real time (WebSocket)**

Connect to:

```
ws://localhost:8000/graph/ws/{run_id}
```

You will receive:

* log entries for each node execution
* a final completion message containing final state

Works perfectly with Postman WebSocket, Web browser, or command-line clients.

**What the Engine Supports**

* State flow between nodes
* Conditional branching
* Looping until condition met
* Background/async execution
* Step-by-step logging
* WebSocket streaming
* Simple tool injection
* Clear code structure

**What Could Be Improved with More Time**

* SQLite/Postgres persistence for graphs and runs
* Graph validation on creation
* More defensive error handling
* Tool registration API endpoint
* Unit tests for nodes and engine
* Visual graph representation
* A UI to watch workflow execution live

**Why This Design**

The structure prioritizes:

* clarity
* testability
* correctness
* minimalism
* async behavior
* separation of concerns

It demonstrates backend engineering fundamentals without unnecessary complexity.



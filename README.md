# Skyline Parking RAG (Learning Project)

Lightweight Retrieval-Augmented Generation chatbot for Skyline Belgrade Parking.

Detailed usage documentation is available in `SYSTEM_USAGE.md`.

## Features

- Streamlit chat UI with unified LangGraph orchestration
- Multi-agent pipeline: user interaction → escalation check → admin review
- Chroma vector database for knowledge retrieval
- Reservation booking with pending approval and admin HITL workflow
- MCP server integration for persistent approved reservation storage
- PII anonymization/redaction guardrails via Presidio
- Retrieval evaluation and performance dashboard

## Project Structure

- `main.py`: Streamlit app entrypoint (runs unified orchestrator)
- `orchestrator.py`: master LangGraph pipeline (user → escalation → admin → MCP)
- `user_agent.py`: user chatbot graph (intent routing, RAG, reservation flow)
- `user_tools.py`: user retrieval and reservation tools
- `chat_streamlit.py`: user chat Streamlit renderer
- `admin_agent.py`: admin agent with human-in-the-loop approval middleware
- `admin_tools.py`: admin approval/rejection and MCP persistence call
- `mcp_client.py`: client bridge to MCP server with health checks
- `mcp_server/server.py`: MCP server run entrypoint
- `mcp_server/tools.py`: `save_reservation` MCP tool implementation
- `mcp_server/auth.py`: bearer token authorization
- `mcp_server/validation.py`: reservation payload validation/sanitization
- `security.py`: PII anonymization/redaction via Presidio
- `index_rag.py`: knowledge base indexing into Chroma
- `knowledge.md`: source knowledge base content
- `fake_db.py`: in-memory reservation state storage
- `evaluation/evaluate.py`: retrieval metrics and latency evaluation
- `pages/admin.py`: admin approvals dashboard
- `pages/evaluation.py`: retrieval performance dashboard
- `tests/test_integration.py`: orchestration integration tests
- `tests/load_test.py`: load checks for chatbot/admin/MCP scenarios

## MCP Server Persistence

Approved reservations are persisted via an MCP server boundary:

Admin Decision → `admin_tools.apply_reservation_decision()` → `mcp_client.save_reservation_via_mcp()` → MCP Server → `fake_db_approved_reservations.jsonl`

### Approval and Persistence Flow

1. Admin reviews pending reservation in the Admin page or via agent interaction.
2. Admin clicks "Approve" or agent calls `update_reservation_status(approval)`.
3. `admin_tools.apply_reservation_decision()` updates in-memory `fake_db` to "approved" status.
4. Function calls `save_reservation_via_mcp()` with structured reservation payload.
5. MCP client authenticates using `ADMIN_TOKEN` bearer token.
6. MCP server validates and sanitizes the payload.
7. Approved reservation is appended to `fake_db_approved_reservations.jsonl`.

If approval occurs without MCP connectivity, in-memory state updates but persistent storage fails gracefully.

## Unified Orchestration (LangGraph)

The unified orchestration graph connects all components:

User Chat -> `orchestrator.py` (`master_orchestrator`)
-> User agent graph (`user_agent.py`)
-> Escalation check (`fake_db` pending reservation)
-> Admin agent stage (`admin_agent.py`)
-> Admin decision tools (`admin_tools.py`)
-> MCP persistence (`mcp_client.py` -> `mcp_server/server.py`)

### Graph behavior

1. The user message is processed by the user LangGraph.
2. Orchestrator checks whether the current user thread has a pending, escalated reservation.
3. If escalation is needed, orchestrator calls the admin agent stage to prepare review context.
4. Admin approval/rejection remains human-in-the-loop from the Admin page.
5. On approval, `admin_tools.apply_reservation_decision` calls MCP persistence.

### Why this stays simple

- Reuses existing user/admin graphs and tools.
- Keeps a single persistence boundary in admin tools.
- Avoids duplicate write paths or extra storage layers.

### Storage format

Persisted data is append-only JSONL in `fake_db_approved_reservations.jsonl`.

Each line includes fake_db-aligned fields such as:
- `reservation_id`
- `full_name`
- `numplate`
- `datetime_start`
- `datetime_end`
- `status`
- `created_at`
- `updated_at`
- `approval_time` (server-side timestamp)

### Security behavior

- MCP server fails fast if `ADMIN_TOKEN` is missing.
- Requests must provide `Authorization: Bearer <ADMIN_TOKEN>`.
- Unauthorized requests are rejected.
- Input is sanitized and datetime fields are validated as ISO datetimes.

## Prerequisites

- Python 3.10+
- OpenAI API key

## Setup

1. Create and activate a virtual environment.
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.
```powershell
pip install -r requirements.txt
```

`requirements.txt` is the current full environment snapshot generated from `pip freeze`.

3. Create environment file from template.
```powershell
copy .env_example .env
```

4. Set your API key in `.env`.
```env
OPENAI_API_KEY=your_openai_api_key_here
ADMIN_TOKEN=change_me_admin_token
MCP_SERVER_URL=http://127.0.0.1:8001/mcp
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=8001
MCP_SERVER_PATH=/mcp
```

LangSmith settings from `.env_example` are optional and only needed for offline evaluation with answer-quality metrics.

5. Build the vector index (required before first run).

`chroma_db/` is gitignored, so it is not included in the repository.
You must run indexing locally to create the database.

```powershell
python index_rag.py
```

6. Start MCP server (required for persistent approved reservation storage).

Run in a separate terminal:

```powershell
.\.venv\Scripts\python.exe mcp_server\server.py
```

## Run the App

After building the index and starting the MCP server:

```powershell
streamlit run main.py
```

Open the `Admin` page to review/approve reservations.
If MCP is unreachable, approvals still update in-memory state but persistent write may fail.

`main.py` now runs the unified orchestrator entrypoint.

## Build or Refresh the Vector Index

Run this again after editing `knowledge.md`.

```powershell
python index_rag.py
```

## Evaluation

Run retrieval and latency evaluation:

```powershell
python evaluation/evaluate.py
```

Run LangSmith offline evaluation (answer quality + retrieval + latency):

```powershell
python evaluation/evaluate_langsmith.py
```

LangSmith evaluation is optional and not required for core functionality.

This script uses the LangSmith SDK `evaluate()` flow and creates an experiment
in your LangSmith workspace. It expects these `.env` values:

- `LANGSMITH_TRACING=true`
- `LANGSMITH_API_KEY=...`
- `LANGSMITH_PROJECT=skyline-rag`
- optional `LANGSMITH_WORKSPACE_ID=...` (multi-workspace API keys)
- optional `LANGSMITH_TEST_CACHE=.langsmith_cache` (stable and cheaper reruns)

Optional runtime knobs (via `.env`):

- `EVAL_TOP_K` (default `3`)
- `EVAL_LATENCY_SLA_SECONDS` (default `2.0`)
- `EVAL_MAX_CONCURRENCY` (default `4`)
- `EVAL_NUM_REPETITIONS` (default `1`)
- `LANGSMITH_DATASET` (default `skyline-rag-offline`)
- `LANGSMITH_EXPERIMENT_PREFIX` (default `skyline-rag-2026`)

Optional: regenerate labeled retrieval dataset:

```powershell
python evaluation/test_chunks_lab.py
```

Generated artifacts:

- `evaluation/labeled_dataset.json`
- `evaluation/rag_report.json`

Open Streamlit and navigate to the `Evaluation` page.

## Integration and Load Testing

Run integration tests for orchestration behavior:

```powershell
python -m unittest tests/test_integration.py -v
```

Run load checks with three scenarios (chatbot dialogue, admin confirmation, MCP recording):

```powershell
python tests/load_test.py --iterations 1000
```

These tests focus on fast local validation of core orchestration routing and stability.

## Scope and Limitations

- Demo-oriented, not production hardened.
- Reservation data is in-memory mock data (not persistent across restarts).
- Persistent storage via MCP writes only approved reservations to local JSONL.
- PII vault state is process-local and not isolated for multi-tenant use.
- Orchestrator checkpointing uses in-memory storage (not distributed).
- Evaluation focuses on retrieval metrics, latency, and optional answer quality (LangSmith).

**Note:** Presidio spaCy language model is downloaded automatically on first run.
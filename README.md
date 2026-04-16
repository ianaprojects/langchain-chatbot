# Skyline Parking RAG (Learning Project)

Lightweight Retrieval-Augmented Generation chatbot for Skyline Belgrade Parking.

## Features

- Streamlit chat UI
- LangGraph-based agent flow
- Chroma vector database for knowledge retrieval
- Reservation interaction flow (mock in-memory DB)
- Stage 3 MCP storage boundary for approved reservations
- Basic guardrails for PII anonymization/redaction (Presidio)
- Retrieval evaluation script and dashboard page

## Project Structure

- `main.py`: Streamlit app entrypoint
- `user_agent.py`: user chatbot graph (intent routing, RAG, reservation flow)
- `user_tools.py`: user retrieval and reservation tools
- `chat_streamlit.py`: user chat Streamlit renderer
- `admin_agent.py`: admin agent orchestration
- `admin_tools.py`: admin approval/listing tools
- `mcp_client.py`: client bridge from app/admin tools to MCP server
- `mcp_server/server.py`: MCP server run entrypoint
- `mcp_server/tools.py`: `save_reservation` MCP tool implementation
- `mcp_server/auth.py`: bearer token authorization checks
- `mcp_server/validation.py`: payload validation/sanitization
- `security.py`: PII anonymization/redaction
- `index_rag.py`: knowledge indexing into Chroma
- `knowledge.md`: source knowledge base
- `evaluation/evaluate.py`: retrieval metrics report generation
- `pages/admin.py`: admin approvals page and MCP health warning
- `pages/evaluation.py`: Streamlit evaluation dashboard
- `fake_db_approved_reservations.jsonl`: append-only approved reservation storage

## Stage 3: MCP Storage Integration

Stage 3 introduces a real MCP client/server boundary:

Admin Agent -> `mcp_client.py` -> `mcp_server/server.py` -> `fake_db_approved_reservations.jsonl`

### What happens on approval

1. Admin approves a reservation via direct UI action or admin agent tool call.
2. `admin_tools.apply_reservation_decision` updates in-memory `fake_db` state.
3. If status is `approved`, app calls `save_reservation_via_mcp`.
4. MCP server authorizes request using bearer token from `ADMIN_TOKEN`.
5. `save_reservation` validates/sanitizes payload and appends one JSON line.

Only approved reservations are persisted by MCP.

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

LangSmith settings from `.env_example` are optional for the basic Stage 1 chatbot flow.
They are only needed if you want to enable LangSmith tracing/evaluation as an upgrade on top of the Stage 1 implementation.

5. Build the vector index (required before first run).

`chroma_db/` is gitignored, so it is not included in the repository.
You must run indexing locally to create the database.

```powershell
python index_rag.py
```

6. Start MCP server (required for Stage 3 persistent approved storage).

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

This is an optional evaluation upgrade. The basic Stage 1 implementation does not require LangSmith.

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

## MVP Scope and Limitations

- Demo-oriented, not production hardened.
- Reservation data is in-memory mock data.
- Stage 3 persistence writes only approved reservations to local JSONL storage.
- Privacy vault state is process-local and not isolated for multi-tenant deployments.
- Local script `evaluation/evaluate.py` focuses on retrieval metrics and latency.
- LangSmith script `evaluation/evaluate_langsmith.py` adds answer-quality scoring and experiment tracking.

Presidio needs -> will download it automatically during the initial app run
Installing collected packages: en-core-web-lg
Successfully installed en-core-web-lg-3.8.0
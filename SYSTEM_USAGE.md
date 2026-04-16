# System Usage

This document describes the current implemented behavior of the Skyline Parking RAG system.

## What The System Does

The repository contains a Streamlit application with three main runtime parts:

- User chat application in `main.py`, driven by the unified LangGraph orchestrator in `orchestrator.py`
- Admin review interface in `pages/admin.py`
- MCP storage server in `mcp_server/server.py`

The system supports these implemented flows:

- Answering Skyline Belgrade Parking questions from the local knowledge base in `knowledge.md`
- Creating reservation requests through the user chat flow
- Escalating pending reservation requests to admin review
- Approving or rejecting reservations from the admin page
- Persisting approved reservations through the MCP server into `fake_db_approved_reservations.jsonl`
- Running retrieval evaluation and viewing the generated report in the Evaluation page

## Runtime Components

### User chat flow

`main.py` starts the Streamlit chat UI and passes requests into `master_orchestrator`.

`orchestrator.py` runs a three-stage graph:

1. User interaction through `user_agent`
2. Escalation check against the in-memory reservation state
3. Admin review context preparation when a pending escalated reservation exists

`user_agent.py` implements these behaviors:

- Anonymizes the latest user message with Presidio before processing
- Classifies the request as `info`, `reservation`, `unsafe`, or `unknown`
- Uses retrieval over Chroma for factual parking questions
- Uses reservation tools for booking requests and reservation status checks
- Applies outbound redaction before returning the final assistant response

### Reservation behavior

The implemented reservation tools live in `user_tools.py`.

Current booking behavior:

- `book_parking_spot` is called only after the model has all required fields
- Required booking fields are full name, car plate, start datetime, and end datetime
- Booking creates or updates the reservation in the in-memory fake database
- New or updated booking requests are stored with `pending` status and `escalated_to_admin=True`

Current reservation status behavior:

- `get_user_reservation_status` returns the reservation attached to the current thread id
- If no reservation exists for that thread, the tool returns `Reservation not found`

### Admin flow

The admin page in `pages/admin.py` exposes two paths:

- Direct approve or reject buttons for pending reservations
- An optional natural-language admin assistant backed by `admin_agent.py`

Current admin page behavior:

- It lists only reservations with `pending` status in the main review section
- Each pending item can be approved or rejected with an optional decision note
- Button-based decisions call `apply_reservation_decision` directly
- The page also performs an MCP health check and shows a warning if storage is unavailable

Current admin assistant behavior:

- The agent can list reservations and request approval or rejection by reservation id
- `get_reservations` runs without interruption
- `update_reservation_status` is protected by human-in-the-loop confirmation
- A pending tool call must be explicitly confirmed or rejected in the UI before execution

### MCP server flow

The MCP server is started from `mcp_server/server.py` and exposes the `save_reservation` tool from `mcp_server/tools.py`.

Current persistence behavior:

- The server requires `ADMIN_TOKEN` to be configured before startup
- The client sends a bearer token from `ADMIN_TOKEN`
- Only approved reservations are allowed to be persisted
- The server validates ISO datetime fields and sanitizes text fields
- Each approved reservation is appended as one JSON line to `fake_db_approved_reservations.jsonl`

If approval succeeds in the admin layer but the MCP write fails, the in-memory reservation status still changes and the failure is returned to the caller.

### Evaluation flow

The repository includes two evaluation scripts:

- `evaluation/evaluate.py` computes retrieval and latency metrics and writes `evaluation/rag_report.json`
- `evaluation/evaluate_langsmith.py` runs an optional LangSmith evaluation using the local labeled dataset

The Streamlit Evaluation page in `pages/evaluation.py` reads only `evaluation/rag_report.json`.

## Data And State

### Knowledge base and vector index

- Source content lives in `knowledge.md`
- `index_rag.py` splits that file by Markdown headers and rebuilds the Chroma index in `chroma_db`
- `user_tools.py` loads the persisted Chroma database from `./chroma_db`

The index must exist locally before the chat application can use retrieval.

### Reservation state

- Runtime reservation state is held in-memory in `fake_db.py`
- The fake database is preloaded with three example reservations: one pending, one approved, and one rejected
- In-memory reservation state is not persistent across process restarts
- Only approved reservations are persisted to the JSONL file through the MCP server

### PII handling

`security.py` implements the current PII flow:

- Input text is analyzed with Presidio
- Person names and Serbian license plates are tokenized into local vault placeholders
- The UI deanonymizes placeholders for display
- Outbound redaction keeps names visible in the UI but still redacts other supported sensitive entities such as phone numbers, email addresses, and credit cards

## Setup

### Prerequisites

- Python 3.10+
- A valid OpenAI API key

### Install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configure environment variables

Copy `.env_example` to `.env` and set the values used by the application:

```env
OPENAI_API_KEY=your_openai_api_key_here
ADMIN_TOKEN=change_me_admin_token
MCP_SERVER_URL=http://127.0.0.1:8001/mcp
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=8001
MCP_SERVER_PATH=/mcp
```

Optional LangSmith settings are listed in `.env_example` and are used only by `evaluation/evaluate_langsmith.py`.

### Build the vector index

Run this before the first chat session and after editing `knowledge.md`:

```powershell
python index_rag.py
```

If `chroma_db` is locked by another process, the script exits and asks you to close running app sessions before retrying.

## Running The System

### 1. Start the MCP server

Run this in a separate terminal:

```powershell
.\.venv\Scripts\python.exe mcp_server\server.py
```

### 2. Start the Streamlit app

```powershell
streamlit run main.py
```

The app exposes the main chat page plus the Streamlit pages under `pages/`.

### 3. Use the user chat

Current implemented chat usage:

- Ask factual Skyline Belgrade Parking questions to trigger retrieval over the Chroma index
- Start a booking request by providing or confirming the required booking fields
- Ask for reservation status to retrieve the current thread's reservation state

When a reservation request is created, the orchestrator checks the in-memory reservation store. If the current thread has a `pending` reservation marked for escalation, the user receives a message that the request was escalated to admin review.

### 4. Use the Admin page

Open the `Admin` page in Streamlit.

Current implemented admin usage:

- Review pending reservations shown in the page
- Approve or reject a request directly with the page buttons
- Optionally send natural-language commands to the admin assistant
- Confirm or reject any interrupted admin tool call in the UI

### 5. Use the Evaluation page

Generate the report first:

```powershell
python evaluation/evaluate.py
```

Then open the `Evaluation` page in Streamlit to inspect the saved report.

## Testing And Validation

### Integration tests

```powershell
python -m unittest tests/test_integration.py -v
```

These tests cover the orchestrator routing logic, including escalation and per-thread behavior.

### Load checks

```powershell
python tests/load_test.py --iterations 1000
```

This script runs the three scenarios implemented in `tests/load_test.py`:

- Chatbot dialogue path through the orchestrator
- Admin confirmation path through reservation decision handling
- MCP recording path through approval-time persistence calls

### Optional LangSmith evaluation

```powershell
python evaluation/evaluate_langsmith.py
```

This path depends on LangSmith environment variables being configured.

## Current Limitations

These limitations are present in the current implementation:

- Reservation runtime state is in-memory only
- Approved reservations are the only records persisted to disk
- Orchestrator and agent checkpointing use in-memory storage
- MCP persistence writes to a local JSONL file, not a database
- The evaluation page depends on `evaluation/rag_report.json` already existing
- The system is scoped to Skyline Belgrade Parking requests only
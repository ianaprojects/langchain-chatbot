# Skyline Parking RAG (Learning Project)

Lightweight Retrieval-Augmented Generation chatbot for Skyline Belgrade Parking.

## Features

- Streamlit chat UI
- LangGraph-based agent flow
- Chroma vector database for knowledge retrieval
- Reservation interaction flow (mock in-memory DB)
- Basic guardrails for PII anonymization/redaction (Presidio)
- Retrieval evaluation script and dashboard page

## Project Structure

- `main.py`: Streamlit app entrypoint
- `user_agent.py`: user chatbot graph (intent routing, RAG, reservation flow)
- `user_tools.py`: user retrieval and reservation tools
- `user_chat_streamlit.py`: user chat Streamlit renderer
- `admin_agent.py`: admin agent orchestration
- `admin_tools.py`: admin approval/listing tools
- `security.py`: PII anonymization/redaction
- `index_rag.py`: knowledge indexing into Chroma
- `knowledge.md`: source knowledge base
- `evaluation/evaluate.py`: retrieval metrics report generation
- `pages/evaluation.py`: Streamlit evaluation dashboard

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

3. Create environment file from template.
```powershell
copy .env_example .env
```

4. Set your API key in `.env`.
```env
OPENAI_API_KEY=your_openai_api_key_here
```

5. Build the vector index (required before first run).

`chroma_db/` is gitignored, so it is not included in the repository.
You must run indexing locally to create the database.

```powershell
python index_rag.py
```

## Run the App

After building the index:

```powershell
streamlit run main.py
```

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
- Privacy vault state is process-local and not isolated for multi-tenant deployments.
- Evaluation focuses on retrieval metrics (Precision@K, Recall@K, F1) and latency, not full answer quality benchmarking.

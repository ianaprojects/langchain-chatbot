# Skyline Parking RAG (Learning Project)

Lightweight RAG assistant with:
- chat app (Streamlit)
- Chroma indexing
- retrieval/performance evaluation
- evaluation dashboard page

## Quick Start

1. Activate venv
```powershell
.\.venv\Scripts\Activate.ps1
```

2. Run app
```powershell
streamlit run main.py
```

3. (Optional) Rebuild vector index after editing `knowledge.md`
```powershell
python index_rag.py
```

## Evaluation

Run evaluation script:
```powershell
python evaluation/evaluate.py
```

Generated evaluation artifacts:
- `evaluation/labeled_dataset.json`
- `evaluation/rag_report.json`

Open Streamlit app and go to **Evaluation** page to view metrics.

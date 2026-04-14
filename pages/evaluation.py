import json
from datetime import datetime
from pathlib import Path
import streamlit as st


REPORT_PATH = Path(__file__).resolve().parent.parent / "evaluation" / "rag_report.json"


def load_report() -> dict | None:
    if not REPORT_PATH.exists():
        return None

    with open(REPORT_PATH, "r", encoding="utf-8") as report_file:
        return json.load(report_file)


def build_table_rows(report: dict) -> list[dict]:
    rows = []
    for item in report.get("per_query_metrics", []):
        retrieval = item.get("retrieval_metrics", {})
        performance = item.get("performance_metrics", {})
        rows.append(
            {
                "query": item.get("query", ""),
                "precision": round(retrieval.get("precision", 0.0), 3),
                "recall": round(retrieval.get("recall", 0.0), 3),
                "f1": round(retrieval.get("f1", 0.0), 3),
                "latency_sec": round(performance.get("latency_sec", 0.0), 3),
                "num_docs": performance.get("num_docs", 0),
                "empty": performance.get("empty", False),
            }
        )
    return rows


st.set_page_config(page_title="RAG Evaluation", page_icon="📊", layout="wide")
st.title("RAG Evaluation")
st.caption("Lightweight dashboard for retrieval and performance metrics")

report = load_report()
if report is None:
    st.warning("Report file not found. Run evaluation/evaluate.py to generate evaluation/rag_report.json.")
    st.stop()

report_mtime = datetime.fromtimestamp(REPORT_PATH.stat().st_mtime)
st.caption(f"Report updated: {report_mtime:%Y-%m-%d %H:%M:%S}")

retrieval_metrics = report.get("retrieval_metrics", {})
performance_metrics = report.get("performance_metrics", {})
table_rows = build_table_rows(report)

col1, col2, col3 = st.columns(3)
col1.metric(f"Precision@{retrieval_metrics.get('k', '-')}", f"{retrieval_metrics.get('precision', 0.0):.3f}")
col2.metric("Recall", f"{retrieval_metrics.get('recall', 0.0):.3f}")
col3.metric("F1", f"{retrieval_metrics.get('f1', 0.0):.3f}")

col4, col5, col6 = st.columns(3)
col4.metric("Avg latency", f"{performance_metrics.get('avg_latency_sec', 0.0):.3f}s")
col5.metric("Avg docs", f"{performance_metrics.get('avg_docs', 0.0):.2f}")
col6.metric("Empty rate", f"{performance_metrics.get('empty_rate', 0.0):.2%}")

st.subheader("Per-query metrics")
st.dataframe(table_rows, width='stretch', hide_index=True)

with st.expander("Raw report"):
    st.json(report)
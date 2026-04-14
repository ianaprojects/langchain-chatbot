import json
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools import retriever

# =========================
# CONFIG
# =========================
DATASET_PATH = BASE_DIR / "labeled_dataset.json"
REPORT_PATH = BASE_DIR / "rag_report.json"
K = 3

def normalize_query(query: str) -> str:
    return " ".join(query.strip().split())

# =========================
# LOAD DATASET
# =========================
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)

# =========================
# METRICS
# =========================
def precision_at_k(retrieved, relevant, k):
    retrieved_k = retrieved[:k]
    hits = len(set(retrieved_k) & set(relevant))
    return hits / k if k > 0 else 0

def recall_at_k(retrieved, relevant, k):
    retrieved_k = retrieved[:k]
    hits = len(set(retrieved_k) & set(relevant))
    return hits / len(relevant) if relevant else 0

def f1(p, r):
    if p + r == 0:
        return 0
    return 2 * (p * r) / (p + r)


def measure_retrieval(active_retriever, query: str):
    start = time.time()
    docs = active_retriever.invoke(query)
    end = time.time()
    return docs, end - start

# =========================
# EVALUATION
# =========================
results = []
performance_logs = []
per_query_metrics = []

for item in dataset:
    query = item["query"]
    relevant_ids = item["relevant_ids"]

    normalized_query = normalize_query(query)
    search_query = normalized_query

    docs, latency = measure_retrieval(retriever, search_query)

    retrieved_ids = [
        d.metadata.get("chunk_id")
        for d in docs
        if d.metadata.get("chunk_id") is not None
    ]

    p = precision_at_k(retrieved_ids, relevant_ids, K)
    r = recall_at_k(retrieved_ids, relevant_ids, K)
    f = f1(p, r)

    results.append({
        "query": query,
        "precision": p,
        "recall": r,
        "f1": f
    })

    performance_logs.append({
        "query": query,
        "latency_sec": latency,
        "num_docs": len(docs),
        "empty": len(docs) == 0
    })

    per_query_metrics.append({
        "query": query,
        "retrieval_metrics": {
            "precision": p,
            "recall": r,
            "f1": f,
        },
        "performance_metrics": {
            "latency_sec": latency,
            "num_docs": len(docs),
            "empty": len(docs) == 0,
        },
    })

# =========================
# PRINT RESULTS
# =========================
print("\n=== PER QUERY ===")
for r in results:
    print(f"\nQuery: {r['query']}")
    print(f"P@{K}: {r['precision']:.2f}")
    print(f"R@{K}: {r['recall']:.2f}")
    print(f"F1:   {r['f1']:.2f}")

# =========================
# AVERAGES
# =========================
avg_p = sum(r["precision"] for r in results) / len(results)
avg_r = sum(r["recall"] for r in results) / len(results)
avg_f = sum(r["f1"] for r in results) / len(results)

print("\n=== AVERAGE ===")
print(f"Precision@{K}: {avg_p:.2f}")
print(f"Recall@{K}:    {avg_r:.2f}")
print(f"F1:            {avg_f:.2f}")

# =========================
# PERFORMANCE
# =========================
avg_latency = sum(p["latency_sec"] for p in performance_logs) / len(performance_logs)
avg_docs = sum(p["num_docs"] for p in performance_logs) / len(performance_logs)
empty_rate = sum(1 for p in performance_logs if p["empty"]) / len(performance_logs)

print("\n=== PERFORMANCE ===")
print(f"Avg latency: {avg_latency:.3f}s")
print(f"Avg docs retrieved: {avg_docs:.2f}")
print(f"Empty retrieval rate: {empty_rate:.2%}")

print("\n=== PER QUERY PERFORMANCE ===")
for p in performance_logs:
    print(f"\nQuery: {p['query']}")
    print(f"Latency: {p['latency_sec']:.3f}s")
    print(f"Docs retrieved: {p['num_docs']}")
    print(f"Empty: {p['empty']}")

# =========================
# FINAL REPORT
# =========================
final_report = {
    "retrieval_metrics": {
        "k": K,
        "precision": avg_p,
        "recall": avg_r,
        "f1": avg_f,
    },
    "performance_metrics": {
        "avg_latency_sec": avg_latency,
        "avg_docs": avg_docs,
        "empty_rate": empty_rate,
    },
    "per_query_metrics": per_query_metrics,
}

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    json.dump(final_report, f, indent=2)

print(f"\nSaved report to {REPORT_PATH}")
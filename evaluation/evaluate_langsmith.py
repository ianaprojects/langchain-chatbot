import json
import importlib.util
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langsmith import Client, traceable

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from user_tools import normalize_query, retriever

load_dotenv()

DATASET_PATH = BASE_DIR / "labeled_dataset.json"
TOP_K = int(os.getenv("EVAL_TOP_K", "3"))
LATENCY_SLA_SECONDS = float(os.getenv("EVAL_LATENCY_SLA_SECONDS", "2.0"))
MAX_CONCURRENCY = int(os.getenv("EVAL_MAX_CONCURRENCY", "4"))
NUM_REPETITIONS = int(os.getenv("EVAL_NUM_REPETITIONS", "1"))
DATASET_NAME = os.getenv("LANGSMITH_DATASET", "skyline-rag-offline")
EXPERIMENT_PREFIX = os.getenv("LANGSMITH_EXPERIMENT_PREFIX", "skyline-rag-2026")

# Keep temperature fixed to reduce run-to-run variance.
ANSWER_MODEL = ChatOpenAI(model="gpt-5-mini", temperature=0)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _token_f1(actual: str, expected: str) -> float:
    a = _tokenize(actual)
    b = _tokenize(expected)
    if not a or not b:
        return 0.0
    overlap = len(set(a) & set(b))
    if overlap == 0:
        return 0.0
    precision = overlap / len(set(a))
    recall = overlap / len(set(b))
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = int(round((len(ordered) - 1) * p))
    index = max(0, min(index, len(ordered) - 1))
    return ordered[index]


def _load_local_dataset() -> list[dict[str, Any]]:
    with DATASET_PATH.open("r", encoding="utf-8") as f:
        rows = json.load(f)

    validated: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        query = str(row.get("query", "")).strip()
        if not query:
            raise ValueError(f"Missing query at row {idx}")

        relevant_ids = row.get("relevant_ids", [])
        if not isinstance(relevant_ids, list):
            raise ValueError(f"relevant_ids must be a list at row {idx}")

        expected_answer = str(row.get("expected_answer", "")).strip()
        if not expected_answer:
            raise ValueError(
                "expected_answer is required for LangSmith answer-quality eval. "
                f"Missing at row {idx} for query: {query}"
            )

        validated.append(
            {
                "query": query,
                "expected_answer": expected_answer,
                "relevant_ids": relevant_ids,
            }
        )

    return validated


def _ensure_langsmith_dataset(client: Client, rows: list[dict[str, Any]]) -> str:
    try:
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        return dataset.name
    except Exception:
        pass

    dataset = client.create_dataset(
        dataset_name=DATASET_NAME,
        description=(
            "Skyline offline RAG benchmark (query, expected_answer, relevant_ids). "
            "Created automatically from evaluation/labeled_dataset.json."
        ),
    )

    examples = [
        {
            "inputs": {"query": row["query"]},
            "outputs": {
                "expected_answer": row["expected_answer"],
                "relevant_ids": row["relevant_ids"],
            },
            "metadata": {"source": "local_json", "index": idx},
        }
        for idx, row in enumerate(rows)
    ]

    client.create_examples(dataset_id=dataset.id, examples=examples)
    return dataset.name


@traceable(name="skyline_rag_target")
def rag_target(inputs: dict[str, Any]) -> dict[str, Any]:
    query = normalize_query(str(inputs.get("query", "")))

    started = time.perf_counter()
    docs = retriever.invoke(query)
    latency_sec = time.perf_counter() - started

    retrieved_ids = [
        d.metadata.get("chunk_id") for d in docs if d.metadata.get("chunk_id") is not None
    ]

    if not docs:
        return {
            "answer": "I do not know based on the available information.",
            "retrieved_ids": [],
            "latency_sec": latency_sec,
        }

    unique_chunks: list[str] = []
    seen: set[str] = set()
    for doc in docs:
        content = doc.page_content
        if content not in seen:
            seen.add(content)
            unique_chunks.append(content)

    context = "\n\n".join(unique_chunks)

    prompt = [
        SystemMessage(
            content=(
                "You answer only from provided context. "
                "If unknown from context, answer exactly: "
                "I do not know based on the available information."
            )
        ),
        HumanMessage(content=f"Question: {query}\n\nContext:\n{context}"),
    ]
    answer = ANSWER_MODEL.invoke(prompt).content

    return {
        "answer": str(answer),
        "retrieved_ids": retrieved_ids[:TOP_K],
        "latency_sec": latency_sec,
    }


def eval_answer_token_f1(outputs: dict, reference_outputs: dict) -> dict[str, Any]:
    score = _token_f1(outputs.get("answer", ""), reference_outputs.get("expected_answer", ""))
    return {"key": "answer_token_f1", "score": score}


def eval_retrieval_recall(outputs: dict, reference_outputs: dict) -> dict[str, Any]:
    retrieved = outputs.get("retrieved_ids", []) or []
    relevant = reference_outputs.get("relevant_ids", []) or []
    if not relevant:
        return {"key": "retrieval_recall_at_k", "score": 1.0}
    score = len(set(retrieved) & set(relevant)) / len(set(relevant))
    return {"key": "retrieval_recall_at_k", "score": score}


def eval_latency_sla(outputs: dict) -> dict[str, Any]:
    latency_sec = float(outputs.get("latency_sec", 0.0))
    return {
        "key": "latency_under_sla",
        "score": 1 if latency_sec <= LATENCY_SLA_SECONDS else 0,
        "comment": f"latency={latency_sec:.3f}s, sla={LATENCY_SLA_SECONDS:.3f}s",
    }


def summary_answer_token_f1(outputs: list[dict], reference_outputs: list[dict]) -> dict[str, Any]:
    if not outputs:
        return {"key": "summary_answer_token_f1", "score": 0.0}
    scores = [
        _token_f1(
            out.get("answer", ""),
            ref.get("expected_answer", ""),
        )
        for out, ref in zip(outputs, reference_outputs)
    ]
    return {"key": "summary_answer_token_f1", "score": sum(scores) / len(scores)}


def summary_retrieval_recall(outputs: list[dict], reference_outputs: list[dict]) -> dict[str, Any]:
    if not outputs:
        return {"key": "summary_retrieval_recall_at_k", "score": 0.0}

    scores: list[float] = []
    for out, ref in zip(outputs, reference_outputs):
        retrieved = out.get("retrieved_ids", []) or []
        relevant = ref.get("relevant_ids", []) or []
        if not relevant:
            scores.append(1.0)
            continue
        scores.append(len(set(retrieved) & set(relevant)) / len(set(relevant)))

    return {"key": "summary_retrieval_recall_at_k", "score": sum(scores) / len(scores)}


def summary_latency_p95(outputs: list[dict]) -> dict[str, Any]:
    latencies = [float(out.get("latency_sec", 0.0)) for out in outputs]
    return {"key": "summary_latency_p95_sec", "score": _percentile(latencies, 0.95)}


def run_langsmith_evaluation() -> None:
    rows = _load_local_dataset()

    # LangSmith caching requires optional vcrpy dependency.
    if os.getenv("LANGSMITH_TEST_CACHE") and importlib.util.find_spec("vcr") is None:
        print(
            "LANGSMITH_TEST_CACHE is set, but vcrpy is not installed. "
            "Proceeding without cache."
        )
        os.environ.pop("LANGSMITH_TEST_CACHE", None)

    client = Client()
    dataset_name = _ensure_langsmith_dataset(client, rows)

    metadata = {
        "models": ["openai:gpt-5-mini"],
        "prompts": ["local:skyline-rag-answer-only-from-context"],
        "tools": [{"name": "retriever", "type": "chroma", "k": TOP_K}],
        "dataset_file": str(DATASET_PATH),
        "latency_sla_seconds": LATENCY_SLA_SECONDS,
    }

    results = client.evaluate(
        rag_target,
        data=dataset_name,
        evaluators=[
            eval_answer_token_f1,
            eval_retrieval_recall,
            eval_latency_sla,
        ],
        summary_evaluators=[
            summary_answer_token_f1,
            summary_retrieval_recall,
            summary_latency_p95,
        ],
        experiment_prefix=EXPERIMENT_PREFIX,
        description="Skyline RAG offline quality + retrieval + latency (LangSmith)",
        max_concurrency=MAX_CONCURRENCY,
        num_repetitions=NUM_REPETITIONS,
        metadata=metadata,
    )

    print("LangSmith evaluation completed.")
    print(f"Dataset: {dataset_name}")

    experiment_name = getattr(results, "experiment_name", None)
    if experiment_name:
        print(f"Experiment: {experiment_name}")

    experiment_url = getattr(results, "url", None)
    if experiment_url:
        print(f"URL: {experiment_url}")


if __name__ == "__main__":
    run_langsmith_evaluation()

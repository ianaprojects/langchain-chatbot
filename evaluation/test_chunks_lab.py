import json
from pathlib import Path
import pandas as pd
from langchain_openai import ChatOpenAI
import chromadb
from dotenv import load_dotenv

load_dotenv()
# =========================
# CONFIG
# =========================
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
CHROMA_PATH = PROJECT_ROOT / "chroma_db"
COLLECTION_NAME = "langchain"
CSV_PATH = BASE_DIR / "queries.csv"
OUTPUT_PATH = BASE_DIR / "labeled_dataset.json"

# =========================
# INIT
# =========================
client = chromadb.PersistentClient(path=str(CHROMA_PATH))
collection = client.get_collection(name=COLLECTION_NAME)

judge = ChatOpenAI(model="gpt-5-mini", temperature=0)

# =========================
# LOAD ALL CHUNKS
# =========================
results = collection.get(include=["documents", "metadatas"])

chunks = []
for i in range(len(results["documents"])):
    chunks.append({
        "id": results["ids"][i],
        "text": results["documents"][i]
    })

print(f"Loaded {len(chunks)} chunks")

# =========================
# LOAD DATASET
# =========================
df = pd.read_csv(
    str(CSV_PATH),
    encoding="utf-8",
    sep=",",
    engine="python"
)

queries = df["queries"].tolist()

# =========================
# LLM JUDGE
# =========================
def is_relevant(query, chunk_text):
    prompt = f"""
Question: {query}

Chunk:
{chunk_text}

Is this chunk directly useful for answering the question?

Answer ONLY "yes" or "no".
Be strict: answer "yes" only if the chunk contains specific relevant information.
"""
    try:
        response = judge.invoke(prompt).content.lower()
        return "yes" in response
    except Exception as e:
        print(f"  ⚠️ Error checking relevance: {e}")
        return False

def generate_expected_answer(query, relevant_chunks):
    """Generate an answer based on relevant chunks using the LLM judge."""
    if not relevant_chunks:
        return "I do not know based on the available information."
    
    context = "\n\n".join(relevant_chunks)
    prompt = f"""Question: {query}

Context:
{context}

Answer the question directly based ONLY on the provided context.
If the context does not contain enough information, answer: "I do not know based on the available information."
Keep the answer concise and factual."""
    
    try:
        response = judge.invoke(prompt).content.strip()
        return response
    except Exception as e:
        print(f"  ⚠️ Error generating answer: {e}")
        return "I do not know based on the available information."

# =========================
# AUTO LABELING
# =========================
labeled_data = []

for idx, query in enumerate(queries):
    print(f"\nProcessing [{idx+1}/{len(queries)}]: {query}")

    relevant_ids = []
    relevant_texts = []

    for chunk_idx, chunk in enumerate(chunks):
        print(f"  Checking chunk {chunk_idx+1}/{len(chunks)}...", end="", flush=True)
        if is_relevant(query, chunk["text"]):
            relevant_ids.append(chunk["id"])
            relevant_texts.append(chunk["text"])
            print(" ✓ relevant")
        else:
            print(" ✗")

    # fallback if no relevant chunks found
    if len(relevant_ids) == 0:
        print("  ⚠️ No relevant chunks found")
        expected_answer = "I do not know based on the available information."
    else:
        print(f"  Generating answer from {len(relevant_ids)} relevant chunks...")
        expected_answer = generate_expected_answer(query, relevant_texts)
        print(f"  Answer: {expected_answer[:80]}...")

    labeled_data.append({
        "query": query,
        "expected_answer": expected_answer,
        "relevant_ids": relevant_ids
    })

# =========================
# SAVE JSON
# =========================
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(labeled_data, f, indent=2, ensure_ascii=False)

print(f"\nSaved labeled dataset to {OUTPUT_PATH}")
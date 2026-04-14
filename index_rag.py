import os
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

from dotenv import load_dotenv
load_dotenv()
# Configuration
DB_PATH = "./chroma_db"
SOURCE_FILE = "knowledge.md"

def index_docs():
    if not os.path.exists(SOURCE_FILE):
        print(f"Error: {SOURCE_FILE} not found!")
        return

    # 1. Split
    headers = [
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]

    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers)
    with open(SOURCE_FILE, "r", encoding="utf-8") as source:
        docs = splitter.split_text(source.read())

    if not docs:
        print("No chunks were created from the source file.")
        return

    ids = []

    for i, doc in enumerate(docs):
        chunk_id = f"chunk_{i}"
        doc.metadata["chunk_id"] = chunk_id
        ids.append(chunk_id)

    # 2. Use Embeddings
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    # 3. Save to Chroma
    # Clear old DB if exists to avoid duplicates
    if os.path.exists(DB_PATH):
        import shutil
        try:
            shutil.rmtree(DB_PATH)
        except PermissionError:
            print(
                "Could not rebuild index because chroma_db is locked by another process. "
                "Close running app sessions and retry indexing."
            )
            return

    vectorstore = Chroma.from_documents(
        documents=docs, 
        embedding=embeddings, 
        persist_directory=DB_PATH,
        ids=ids
    )
    print(f"Successfully indexed {len(docs)} chunks into {DB_PATH}")

if __name__ == "__main__":
    index_docs()
# tools.py
from langchain.tools import tool, ToolRuntime
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from security import protector
from fake_db import ReservationData, fake_db_instance, debug_print_fake_db
from dataclasses import replace
from datetime import datetime as dt
from dotenv import load_dotenv
load_dotenv()

# Initialize embeddings
embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

# Load existing DB
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={
        "k": 3
    }
)


def _normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


@tool
def debug_runtime_info(runtime: ToolRuntime):
    """
    Debug tool.

    Use only when the user explicitly asks for runtime or thread diagnostics.
    Returns runtime object details for the current execution context.
    """
    
    print(runtime.config["configurable"]["thread_id"])

    return runtime

@tool
def book_parking_spot(full_name: str, car_plate: str, date_start: dt, date_end: dt, runtime: ToolRuntime):
    """
    Create or update a booking request for Skyline Belgrade Parking.

    Call this tool only when all required fields are known:
    - full_name: user full name
    - car_plate: vehicle plate number
    - date_start: reservation start datetime
    - date_end: reservation end datetime

    Do not call this tool with partial booking data.
    """
    # Resolve anonymized placeholders to real values stored in local vault.
    real_name = protector.get_real_value(full_name)
    real_plate = protector.get_real_value(car_plate)

    reservation_id=runtime.config["configurable"]["thread_id"]

    upsert_reservation(
        reservation_id,
        full_name=real_name,
        numplate=real_plate,
        datetime_start=date_start,
        datetime_end=date_end,
        status="pending",
    )

    return f"Success! Booking request created for {full_name}. Current status: pending."


@tool
def get_user_reservation_status(runtime: ToolRuntime) -> str:
    """
    Return reservation status for the current thread/user.

    Use when the user asks about booking state, for example:
    - "Is my reservation approved?"
    - "What is my reservation status?"

    Returns one of:
    - "pending"
    - "approved"
    - "rejected"
    - "Reservation not found"
    """
    thread_id = runtime.config["configurable"]["thread_id"]

    res = fake_db_instance.get(thread_id)
    
    if res:
        return res.status
    
    return "Reservation not found"


@tool
def search_parking_info(query: str):
    """
    Search Skyline Belgrade Parking knowledge base.

    Call this tool for factual questions about parking information, such as:
    - location and address
    - working hours
    - pricing
    - parking rules and limits
    - safety/security

    Requirements:
    - `query` must be non-empty
    - `query` must be a short, natural question or keyword phrase (max ~10 words)
    - Do NOT expand or paraphrase the query — pass the user's question as-is
    - `query` should be in English
    """

    if not query or not query.strip():
        return "Search request must include a non-empty query."

    normalized_query = _normalize_query(query)
    # Truncate to protect retrieval quality against over-expanded LLM queries
    search_query = normalized_query[:120]

    # Vector search
    docs = retriever.invoke(search_query)
    
    if not docs:
        return "No specific information found in the knowledge base."

    seen_contents = set()
    unique_contents = []
    for doc in docs:
        if doc.page_content not in seen_contents:
            seen_contents.add(doc.page_content)
            unique_contents.append(doc.page_content)

    return "\n\n".join(unique_contents)




def upsert_reservation(reservation_id, **kwargs):
    if reservation_id in fake_db_instance:
        current = fake_db_instance[reservation_id]
        updates = {k: v for k, v in kwargs.items() if v is not None}
        updates["updated_at"] = dt.now()
        fake_db_instance[reservation_id] = replace(current, **updates)
        debug_print_fake_db("[fake_db:update]")
        return f"Updated reservation with ID: {reservation_id}"
    else:
        fake_db_instance[reservation_id] = ReservationData(**kwargs)
        debug_print_fake_db("[fake_db:create]")
        return f"Reservation created with ID: {reservation_id}"




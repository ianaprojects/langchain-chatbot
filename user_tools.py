# user_tools.py
from dataclasses import replace
from datetime import datetime as dt

from dotenv import load_dotenv
from langchain.tools import ToolRuntime, tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from fake_db import ReservationData, debug_print_fake_db, fake_db_instance
from security import protector

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


def normalize_query(query: str) -> str:
    return " ".join(query.strip().split())


@tool
def debug_runtime_info(runtime: ToolRuntime):
    """
    Debug tool.

    Use only when the user explicitly asks for runtime or thread diagnostics.
    Returns runtime object details for the current execution context.
    """
    thread_id = runtime.config["configurable"].get("thread_id")
    print(thread_id)
    return {"thread_id": thread_id}


@tool
def book_parking_spot(
    full_name: str,
    numplate: str,
    datetime_start: dt,
    datetime_end: dt,
    runtime: ToolRuntime,
):
    """
    Create or update a booking request for Skyline Belgrade Parking.

    Call this tool only when all required fields are known:
    - full_name: user full name
    - numplate: vehicle plate number
    - datetime_start: reservation start datetime
    - datetime_end: reservation end datetime

    Do not call this tool with partial booking data.
    """
    # Resolve anonymized placeholders to real values stored in local vault.
    real_name = protector.get_real_value(full_name)
    real_numplate = protector.get_real_value(numplate)

    reservation_id = runtime.config["configurable"]["thread_id"]

    upsert_reservation(
        reservation_id,
        full_name=real_name,
        numplate=real_numplate,
        datetime_start=datetime_start,
        datetime_end=datetime_end,
        status="pending",
        escalated_to_admin=True,
        escalated_at=dt.now(),
        decided_at=None,
        decision_note="",
    )

    return (
        f"Success! Booking request created for {full_name}. "
        "Your request was sent to an administrator for approval. Current status: pending."
    )


@tool
def get_user_reservation_status(runtime: ToolRuntime) -> str:
    """
    Return reservation details for the current thread/user.

    Use when the user asks about booking state, for example:
    - "Is my reservation approved?"
    - "Show all my reservation details"
    - "What is my reservation status?"

    Returns reservation details (name, plate, start, end, status)
    or "Reservation not found".
    """
    thread_id = runtime.config["configurable"]["thread_id"]

    res = fake_db_instance.get(thread_id)

    if res:
        safe_name = protector.tokenize_value(res.full_name, "PERSON") if res.full_name else "-"
        safe_numplate = protector.tokenize_value(res.numplate, "CAR_PLATE") if res.numplate else "-"
        start = res.datetime_start.isoformat() if res.datetime_start else "-"
        end = res.datetime_end.isoformat() if res.datetime_end else "-"
        return (
            "Reservation details:\n\n"
            f"Name: {safe_name}\n"
            f"Plate: {safe_numplate}\n"
            f"Start: {start}\n"
            f"End: {end}\n"
            f"Status: {res.status}"
        )

    return "Reservation not found"


def upsert_reservation(reservation_id, **kwargs):
    if reservation_id in fake_db_instance:
        current = fake_db_instance[reservation_id]
        updates = {k: v for k, v in kwargs.items() if v is not None}
        updates["updated_at"] = dt.now()
        fake_db_instance[reservation_id] = replace(current, **updates)
        debug_print_fake_db("[fake_db:update]")
        return f"Updated reservation with ID: {reservation_id}"

    fake_db_instance[reservation_id] = ReservationData(**kwargs)
    debug_print_fake_db("[fake_db:create]")
    return f"Reservation created with ID: {reservation_id}"

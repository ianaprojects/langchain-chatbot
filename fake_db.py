from dataclasses import dataclass, field, asdict
from datetime import datetime as dt
import streamlit as st


@dataclass
class ReservationData:
    """In-memory reservation record."""
    full_name: str = ""
    numplate: str = ""
    datetime_start: dt = field(default_factory=dt.now)
    datetime_end: dt = field(default_factory=dt.now)
    status: str = "pending"
    created_at: dt = field(default_factory=dt.now)
    updated_at: dt = field(default_factory=dt.now)


# In-memory fake DB (non-persistent by design).
@st.cache_resource
def init_fake_db():
    return {}


fake_db_instance = init_fake_db()


fake_db_instance["id1"] = ReservationData(full_name="Ivan Petrovic", status="pending")
fake_db_instance["id2"] = ReservationData(full_name="Aleks One", status="approved")
fake_db_instance["id3"] = ReservationData(full_name="Anna Brown", status="pending")


def debug_print_fake_db(prefix: str = "[fake_db]"):
    """Print a readable snapshot of in-memory reservations."""
    print(f"{prefix} records={len(fake_db_instance)}")
    for reservation_id, reservation in fake_db_instance.items():
        print(f"{prefix} {reservation_id}: {asdict(reservation)}")
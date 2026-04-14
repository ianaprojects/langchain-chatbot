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
    escalated_to_admin: bool = False
    escalated_at: dt | None = None
    decided_at: dt | None = None
    decision_note: str = ""
    created_at: dt = field(default_factory=dt.now)
    updated_at: dt = field(default_factory=dt.now)


# In-memory fake DB (non-persistent by design).
@st.cache_resource
def init_fake_db():
    return {}


fake_db_instance = init_fake_db()


fake_db_instance["id1"] = ReservationData(full_name="Ivan Petrovic", status="pending", escalated_to_admin=True, escalated_at=dt.now())
fake_db_instance["id2"] = ReservationData(
    full_name="Aleks One",
    status="approved",
    escalated_to_admin=True,
    escalated_at=dt.now(),
    decided_at=dt.now(),
)
fake_db_instance["id3"] = ReservationData(full_name="Anna Brown", status="pending", escalated_to_admin=True, escalated_at=dt.now())


def debug_print_fake_db(prefix: str = "[fake_db]"):
    """Print a readable snapshot of in-memory reservations."""
    print(f"\n{prefix} ── {len(fake_db_instance)} record(s) ──────────────────")
    for reservation_id, reservation in fake_db_instance.items():
        d = asdict(reservation)
        print(f"  [{reservation_id}]")
        for key, value in d.items():
            print(f"    {key}: {value}")
    print(f"{prefix} ──────────────────────────────────────────────")
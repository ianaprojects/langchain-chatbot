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


fake_db_instance["id1"] = ReservationData(
    full_name="John Carter",
    numplate="BG-123-AB",
    datetime_start=dt(2026, 4, 15, 9, 0),
    datetime_end=dt(2026, 4, 15, 12, 0),
    status="pending",
    escalated_to_admin=True,
    escalated_at=dt(2026, 4, 15, 8, 45),
    decided_at=None,
    decision_note="",
    created_at=dt(2026, 4, 15, 8, 30),
    updated_at=dt(2026, 4, 15, 8, 45),
)
fake_db_instance["id2"] = ReservationData(
    full_name="Mila Novak",
    numplate="NS-987-ZX",
    datetime_start=dt(2026, 4, 16, 14, 30),
    datetime_end=dt(2026, 4, 16, 18, 0),
    status="approved",
    escalated_to_admin=True,
    escalated_at=dt(2026, 4, 16, 12, 0),
    decided_at=dt(2026, 4, 16, 12, 20),
    decision_note="",
    created_at=dt(2026, 4, 16, 11, 40),
    updated_at=dt(2026, 4, 16, 12, 20),
)
fake_db_instance["id3"] = ReservationData(
    full_name="Oliver Smith",
    numplate="KG-555-YY",
    datetime_start=dt(2026, 4, 17, 7, 15),
    datetime_end=dt(2026, 4, 17, 9, 45),
    status="rejected",
    escalated_to_admin=True,
    escalated_at=dt(2026, 4, 17, 6, 40),
    decided_at=dt(2026, 4, 17, 6, 55),
    decision_note="Vehicle access not permitted for selected zone",
    created_at=dt(2026, 4, 17, 6, 20),
    updated_at=dt(2026, 4, 17, 6, 55),
)


def debug_print_fake_db(prefix: str = "[fake_db]"):
    """Print a readable snapshot of in-memory reservations."""
    print(f"\n{prefix} ── {len(fake_db_instance)} record(s) ──────────────────")
    for reservation_id, reservation in fake_db_instance.items():
        d = asdict(reservation)
        print(f"  [{reservation_id}]")
        for key, value in d.items():
            print(f"    {key}: {value}")
    print(f"{prefix} ──────────────────────────────────────────────")
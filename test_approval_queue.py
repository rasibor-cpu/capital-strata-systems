from decimal import Decimal
from postings.approval_queue import build_approval_queue


def main() -> None:
    t1 = {
        "ticket_id": "T-1",
        "status": "SUBMITTED",
        "amount": Decimal("1000.00"),
        "currency": "USD",
        "posting_type": "JOURNAL",
        "maker_user": "m1",
        "submitted_at": "2026-01-01T10:00:00Z",
    }

    t2 = {
        "ticket_id": "T-2",
        "status": "SUBMITTED",
        "amount": Decimal("2500001.00"),
        "currency": "USD",
        "posting_type": "JOURNAL",
        "maker_user": "m2",
        "submitted_at": "2026-01-01T09:00:00Z",
    }

    q = build_approval_queue([t1, t2])
    print("QUEUE:", [(x.ticket_id, x.required_level, str(x.amount)) for x in q])

    assert len(q) == 2
    assert q[0].ticket_id == "T-2"
    assert q[1].ticket_id == "T-1"

    print("OK")


if __name__ == "__main__":
    main()

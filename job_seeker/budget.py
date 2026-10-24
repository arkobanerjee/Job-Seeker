"""Conservative, persistent accounting. Reservations are never automatically refunded."""
import sqlite3
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from uuid import uuid4
from contextlib import contextmanager

class BudgetExceeded(RuntimeError):
    pass


class SpendingLimitExceeded(BudgetExceeded):
    """A normal stop at the saved run allowance."""
    pass

def micros(amount):
    value = Decimal(str(amount))
    if not value.is_finite() or value <= 0:
        raise ValueError("Budget amounts must be finite and positive")
    return int((value * 1_000_000).to_integral_value(rounding=ROUND_CEILING))

class Ledger:
    def __init__(self, path: Path, run_id: str, run_limit=2):
        self.path, self.run_id = path, run_id
        self.limit = micros(run_limit)
        if self.limit > micros(2):
            raise ValueError("Maximum configurable per-run ceiling is $2")
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, run TEXT, kind TEXT, reserved INTEGER, observed REAL, created TEXT DEFAULT CURRENT_TIMESTAMP)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, kind, amount):
        cost = micros(amount)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            current = db.execute("SELECT COALESCE(SUM(reserved),0) FROM reservations WHERE run=?", (self.run_id,)).fetchone()[0]
            if current + cost > self.limit:
                raise SpendingLimitExceeded("Per-run spending threshold reached")
            ident = uuid4().hex
            db.execute("INSERT INTO reservations(id,run,kind,reserved) VALUES(?,?,?,?)", (ident,self.run_id,kind,cost))
        return ident

    def observe(self, ident, usd):
        if usd < 0:
            raise ValueError("Negative usage")
        with self.connect() as db:
            db.execute("UPDATE reservations SET observed=? WHERE id=? AND run=?", (usd,ident,self.run_id))

    def summary(self):
        with self.connect() as db:
            rows = db.execute("SELECT kind,reserved,observed FROM reservations WHERE run=?", (self.run_id,)).fetchall()
            total = db.execute("SELECT COALESCE(SUM(reserved),0) FROM reservations").fetchone()[0]
        return {"reserved_usd": sum(x[1] for x in rows)/1e6,
                "observed_estimate_usd": sum(x[2] or 0 for x in rows),
                "unreconciled_calls": sum(x[2] is None for x in rows),
                "initial_stage_reserved_usd": total/1e6,
                "total_reserved_usd": total/1e6, "run_limit_usd": self.limit/1e6,
                "policy": "per_run", "review_gate_usd": None, "prototype_ceiling_usd": None,
                "note": "Conservative reservations, not a provider invoice. Tavily credits valued at PAYG even if free. Failed/uncertain calls retain reservations."}

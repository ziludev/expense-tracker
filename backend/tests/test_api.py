"""
Backend API tests. Run with: ./venv/bin/pytest tests/

EXPENSE_DB is pointed at a temp file BEFORE importing main so init_db()
creates a throwaway database instead of touching backend/expenses.db.
"""
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

_tmpdir = tempfile.mkdtemp(prefix="expense-test-")
os.environ["EXPENSE_DB"] = str(Path(_tmpdir) / "test.db")

sys.path.insert(0, str(Path(__file__).parent.parent))
import main  # noqa: E402  (must come after EXPENSE_DB is set)

from fastapi.testclient import TestClient  # noqa: E402

client = TestClient(main.app)


# ── Expenses CRUD & validation ────────────────────────────

def test_create_and_get_expense():
    r = client.post("/api/expenses", json={
        "amount": 12.5, "category_id": 1, "date": "2026-07-01", "note": "test",
    })
    assert r.status_code == 200
    exp = r.json()
    assert exp["amount"] == 12.5
    assert exp["category_name"]  # joined category info present

    r2 = client.get(f"/api/expenses/{exp['id']}")
    assert r2.status_code == 200


def test_negative_and_zero_amount_rejected():
    for amount in (-5, 0):
        r = client.post("/api/expenses", json={
            "amount": amount, "category_id": 1, "date": "2026-07-01", "note": "",
        })
        assert r.status_code == 422


def test_non_padded_date_rejected():
    # strptime alone accepts '2026-7-6', which would vanish from LIKE-based stats
    r = client.post("/api/expenses", json={
        "amount": 5, "category_id": 1, "date": "2026-7-6", "note": "",
    })
    assert r.status_code == 422


def test_impossible_date_rejected():
    r = client.post("/api/expenses", json={
        "amount": 5, "category_id": 1, "date": "2026-02-31", "note": "",
    })
    assert r.status_code == 422


def test_unknown_category_is_400():
    r = client.post("/api/expenses", json={
        "amount": 5, "category_id": 99999, "date": "2026-07-01", "note": "",
    })
    assert r.status_code == 400


def test_update_missing_expense_is_404():
    r = client.put("/api/expenses/99999", json={
        "amount": 5, "category_id": 1, "date": "2026-07-01", "note": "",
    })
    assert r.status_code == 404


def test_receipt_path_normalized_to_basename():
    exp = main.ExpenseCreate(amount=1, category_id=1, date="2026-07-06",
                             receipt_path="../../etc/x.png")
    assert exp.receipt_path == "x.png"
    # dot entries must never be stored
    assert main.ExpenseCreate(amount=1, category_id=1, date="2026-07-06",
                              receipt_path="foo/..").receipt_path == ""


def test_page_size_bounded():
    assert client.get("/api/expenses", params={"page_size": -1}).status_code == 422
    assert client.get("/api/expenses", params={"page_size": 999999}).status_code == 422
    assert client.get("/api/expenses", params={"page": 0}).status_code == 422


# ── Stats & month validation ──────────────────────────────

def test_invalid_month_is_400_not_500():
    for month in ("2026-13", "2026-00", "202607", "abcd-ef"):
        r = client.get("/api/stats/summary", params={"month": month})
        assert r.status_code == 400, month
        r = client.get("/api/stats/trend", params={"month": month})
        assert r.status_code == 400, month


def test_budget_rejects_invalid_month_and_amount():
    assert client.post("/api/budgets", json={"month": "2026-13", "amount": 100}).status_code == 422
    assert client.post("/api/budgets", json={"month": "2026-07", "amount": 0}).status_code == 422


def test_elapsed_days_branches():
    today = date(2026, 7, 6)
    assert main._elapsed_days("2026-07", today) == 6    # current month: elapsed days
    assert main._elapsed_days("2026-06", today) == 30   # past month: full month
    assert main._elapsed_days("2026-08", today) == 1    # future month: no div-by-zero
    assert main._elapsed_days("2024-02", today) == 29   # leap February


# ── Receipt serving safety ────────────────────────────────

def test_receipt_traversal_denied():
    r = client.get("/api/receipts/..%2Ftest.db")
    assert r.status_code == 404
    r = client.get("/api/receipts/%2e%2e%2ftest.db")
    assert r.status_code == 404


# ── CSV export ────────────────────────────────────────────

def test_csv_export_bom_and_formula_escape():
    client.post("/api/expenses", json={
        "amount": 9.9, "category_id": 1, "date": "2026-07-02", "note": "=HYPERLINK(evil)",
    })
    r = client.get("/api/export/csv")
    assert r.status_code == 200
    body = r.content.decode("utf-8-sig")  # BOM must be present and consumed
    assert "'=HYPERLINK(evil)" in body    # formula prefixed, not executable

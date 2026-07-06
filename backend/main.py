"""
记账网站后端 — FastAPI + SQLite + PaddleOCR
"""
import calendar
import csv
import io
import logging
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
import uvicorn

# Basic logging so OCR/DB failures can be diagnosed from server output
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("expense-tracker")

BASE_DIR = Path(__file__).parent
# EXPENSE_DB overrides the DB location (used by tests)
DB_PATH = Path(os.environ.get("EXPENSE_DB", BASE_DIR / "expenses.db"))
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Expense Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Database ──────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db():
    """Yield a connection that is always closed, even when a handler raises."""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                emoji TEXT DEFAULT '💰',
                color TEXT DEFAULT '#6b7280',
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                note TEXT DEFAULT '',
                receipt_path TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                month TEXT NOT NULL UNIQUE,
                amount REAL NOT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);
            CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category_id);
        """)
        # 插入默认分类（如果表为空）
        existing = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if existing == 0:
            defaults = [
                ("餐饮", "🍔", "#ef4444"),
                ("交通", "🚗", "#f59e0b"),
                ("购物", "🛍️", "#8b5cf6"),
                ("娱乐", "🎮", "#06b6d4"),
                ("居住", "🏠", "#10b981"),
                ("医疗", "💊", "#ec4899"),
                ("教育", "📚", "#6366f1"),
                ("其他", "💰", "#6b7280"),
            ]
            conn.executemany(
                "INSERT INTO categories (name, emoji, color) VALUES (?, ?, ?)",
                defaults,
            )
        conn.commit()


init_db()


# ── Models ────────────────────────────────────────────────

# Single source of truth for the YYYY-MM month format.
# [0-9] (not \d) rejects Unicode digits; month range 01-12 enforced so
# calendar.monthrange never sees an IllegalMonthError from user input.
MONTH_RE = re.compile(r"[0-9]{4}-(0[1-9]|1[0-2])")


class ExpenseCreate(BaseModel):
    # amount must be positive: stats assume expenses are positive spend
    amount: float = Field(gt=0)
    category_id: int
    date: str  # YYYY-MM-DD
    note: str = ""
    # Filename under uploads/ returned by /api/ocr; empty when no receipt
    receipt_path: str = ""

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        # Strict format check: monthly stats rely on `date LIKE 'YYYY-MM%'`,
        # so a malformed date would silently disappear from all charts.
        # strptime alone is lenient ('2026-7-6' passes), hence the regex too.
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", v):
            raise ValueError("date must be YYYY-MM-DD")
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be a valid YYYY-MM-DD date")
        return v

    @field_validator("receipt_path")
    @classmethod
    def normalize_receipt_path(cls, v: str) -> str:
        # Keep only the basename so client-supplied paths never reach the DB
        if not v:
            return ""
        name = Path(v).name
        # Path("foo/..").name is ".." — never store dot entries
        return "" if name in (".", "..") else name


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1)
    emoji: str = "💰"
    color: str = "#6b7280"


class BudgetSet(BaseModel):
    month: str  # YYYY-MM
    amount: float = Field(gt=0)

    @field_validator("month")
    @classmethod
    def validate_month(cls, v: str) -> str:
        if not MONTH_RE.fullmatch(v):
            raise ValueError("month must be YYYY-MM")
        return v


def _normalize_month(month: str) -> str:
    """Empty means current month; anything else must be YYYY-MM."""
    if not month:
        return datetime.now().strftime("%Y-%m")
    if not MONTH_RE.fullmatch(month):
        raise HTTPException(400, "month must be YYYY-MM")
    return month


# ── Categories API ────────────────────────────────────────

@app.get("/api/categories")
def list_categories():
    with db() as conn:
        rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
        return [dict(r) for r in rows]


@app.post("/api/categories")
def create_category(body: CategoryCreate):
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO categories (name, emoji, color) VALUES (?, ?, ?)",
            (body.name, body.emoji, body.color),
        )
        conn.commit()
        cat = conn.execute("SELECT * FROM categories WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(cat)


@app.put("/api/categories/{cat_id}")
def update_category(cat_id: int, body: CategoryCreate):
    with db() as conn:
        conn.execute(
            "UPDATE categories SET name=?, emoji=?, color=? WHERE id=?",
            (body.name, body.emoji, body.color, cat_id),
        )
        conn.commit()
        cat = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not cat:
            raise HTTPException(404, "Category not found")
        return dict(cat)


@app.delete("/api/categories/{cat_id}")
def delete_category(cat_id: int):
    with db() as conn:
        # Cascade will remove this category's expenses; collect their receipt
        # files first so they don't become orphans on disk
        rows = conn.execute(
            "SELECT receipt_path FROM expenses WHERE category_id=? AND receipt_path != ''",
            (cat_id,),
        ).fetchall()
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit()
        _delete_receipt_files(r["receipt_path"] for r in rows)
        return {"ok": True}


# ── Expenses API ──────────────────────────────────────────

def _delete_receipt_files(names) -> None:
    """Remove receipt files under uploads/ after their DB rows are gone."""
    for name in names:
        p = UPLOAD_DIR / Path(name).name
        if p.is_file():
            p.unlink()
            logger.info("Deleted receipt file %s", p.name)


# Shared SELECT so list/get/create/update all return the same shape
EXPENSE_SELECT = """
    SELECT e.*, c.name AS category_name, c.emoji AS category_emoji, c.color AS category_color
    FROM expenses e
    LEFT JOIN categories c ON e.category_id = c.id
"""


def _fetch_expense(conn: sqlite3.Connection, exp_id: int) -> Optional[sqlite3.Row]:
    return conn.execute(f"{EXPENSE_SELECT} WHERE e.id=?", (exp_id,)).fetchone()


@app.get("/api/expenses")
def list_expenses(
    # Bounded paging: an unbounded/negative LIMIT would dump the whole table
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    keyword: str = "",
    date_from: str = "",
    date_to: str = "",
    sort: str = "date_desc",
):
    conditions = []
    params = []

    if category_id:
        conditions.append("e.category_id = ?")
        params.append(category_id)
    if keyword:
        conditions.append("e.note LIKE ?")
        params.append(f"%{keyword}%")
    if date_from:
        conditions.append("e.date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("e.date <= ?")
        params.append(date_to)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    order = "ORDER BY e.date DESC, e.id DESC" if sort == "date_desc" else "ORDER BY e.date ASC, e.id ASC"

    with db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM expenses e {where}", params
        ).fetchone()[0]

        offset = (page - 1) * page_size
        rows = conn.execute(
            f"{EXPENSE_SELECT} {where} {order} LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@app.get("/api/expenses/{exp_id}")
def get_expense(exp_id: int):
    with db() as conn:
        row = _fetch_expense(conn, exp_id)
        if not row:
            raise HTTPException(404, "Expense not found")
        return dict(row)


@app.post("/api/expenses")
def create_expense(body: ExpenseCreate):
    with db() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO expenses (amount, category_id, date, note, receipt_path) VALUES (?, ?, ?, ?, ?)",
                (body.amount, body.category_id, body.date, body.note, body.receipt_path),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            # FK violation: category_id does not exist
            raise HTTPException(400, "Invalid category_id")
        return dict(_fetch_expense(conn, cur.lastrowid))


@app.put("/api/expenses/{exp_id}")
def update_expense(exp_id: int, body: ExpenseCreate):
    with db() as conn:
        try:
            conn.execute(
                "UPDATE expenses SET amount=?, category_id=?, date=?, note=?, receipt_path=? WHERE id=?",
                (body.amount, body.category_id, body.date, body.note, body.receipt_path, exp_id),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(400, "Invalid category_id")
        exp = _fetch_expense(conn, exp_id)
        if not exp:
            raise HTTPException(404, "Expense not found")
        return dict(exp)


@app.delete("/api/expenses/{exp_id}")
def delete_expense(exp_id: int):
    with db() as conn:
        row = conn.execute("SELECT receipt_path FROM expenses WHERE id=?", (exp_id,)).fetchone()
        conn.execute("DELETE FROM expenses WHERE id=?", (exp_id,))
        conn.commit()
    # Unlink AFTER commit so a failed delete never leaves a row
    # pointing at a missing file
    if row and row["receipt_path"]:
        _delete_receipt_files([row["receipt_path"]])
    return {"ok": True}


# ── OCR API ───────────────────────────────────────────────

# PaddleOCR loads its models on construction (seconds), so build it once
# and reuse. The lock guards against concurrent first-load and against
# concurrent predict() calls, which PaddleOCR does not guarantee to be safe.
_ocr_engine = None
_ocr_lock = threading.Lock()


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from paddleocr import PaddleOCR

        logger.info("Loading PaddleOCR models (first OCR request, may take a while)...")
        _ocr_engine = PaddleOCR(
            text_detection_model_name="PP-OCRv6_small_det",
            text_recognition_model_name="PP-OCRv6_small_rec",
        )
        logger.info("PaddleOCR models loaded")
    return _ocr_engine


ALLOWED_RECEIPT_EXT = {"png", "jpg", "jpeg", "webp", "gif", "bmp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # receipts are photos/screenshots; 10 MB is plenty


@app.post("/api/ocr")
def ocr_receipt(file: UploadFile = File(...)):
    """上传账单图片，返回 OCR 识别结果（receipt_path 为 uploads/ 下的文件名）"""
    # Image extensions only: an .svg/.html upload served back from
    # /api/receipts would execute same-origin (stored XSS)
    raw_ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "png"
    ext = re.sub(r"[^A-Za-z0-9]", "", raw_ext).lower() or "png"
    if ext not in ALLOWED_RECEIPT_EXT:
        raise HTTPException(415, f"Unsupported image type: {ext}")
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}.{ext}"
    filepath = UPLOAD_DIR / filename

    # Stream to disk with a size cap so a huge upload can't fill the disk
    size = 0
    try:
        with open(filepath, "wb") as f:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "Image too large (max 10 MB)")
                f.write(chunk)
    except HTTPException:
        filepath.unlink(missing_ok=True)
        raise

    try:
        with _ocr_lock:
            ocr = _get_ocr()
            result = ocr.predict(str(filepath))
        res = result[0]
        texts = res["rec_texts"]
        scores = [float(s) for s in res["rec_scores"]]

        lines = [
            {"text": text, "confidence": round(score, 4)}
            for text, score in zip(texts, scores)
        ]
        logger.info("OCR ok: %s, %d lines", filename, len(lines))

        return {
            "success": True,
            "lines": lines,
            "receipt_path": filename,
            "suggested_amount": _extract_amount(texts),
            "suggested_date": _extract_date(texts),
        }
    except Exception:
        logger.exception("OCR failed for %s", filename)
        # Generic message: raw exception text may leak paths/library internals
        return {"success": False, "error": "OCR 识别失败，请重试或手动录入", "receipt_path": filename}


def _extract_amount(texts: list[str]) -> Optional[float]:
    """从 OCR 文本中尝试提取金额"""
    for text in texts:
        # 匹配类似 "115.00", "¥115.00", "合计：115.00"
        m = re.search(r"[¥￥]\s*(\d+\.?\d*)", text)
        if m:
            return float(m.group(1))
        # 匹配 "合计" 后的数字
        m = re.search(r"合\s*[计計].*?(\d+\.?\d*)", text)
        if m:
            return float(m.group(1))
    return None


def _extract_date(texts: list[str]) -> Optional[str]:
    """从 OCR 文本中尝试提取日期"""
    for text in texts:
        m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
        if m:
            y, mo, d = m.groups()
            # Zero-pad so the suggestion passes the strict YYYY-MM-DD validator
            return f"{y}-{int(mo):02d}-{int(d):02d}"
    return None


# ── Stats API ─────────────────────────────────────────────

def _elapsed_days(month: str, today: date) -> int:
    """Days to average over: elapsed days for the current month, the full
    month for past months, 1 for future months (avoids division by zero)."""
    days_in_month = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
    current_month = today.strftime("%Y-%m")
    if month == current_month:
        return today.day
    if month < current_month:
        return days_in_month
    return 1


@app.get("/api/stats/summary")
def get_summary(month: str = ""):
    """获取统计摘要：当月总支出、日均、预算进度"""
    month = _normalize_month(month)
    elapsed_days = _elapsed_days(month, date.today())

    with db() as conn:
        total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date LIKE ?",
            (f"{month}%",),
        ).fetchone()[0]
        budget_row = conn.execute(
            "SELECT amount FROM budgets WHERE month=?", (month,)
        ).fetchone()
    budget = budget_row["amount"] if budget_row else 0

    return {
        "month": month,
        "total": round(total, 2),
        "daily_avg": round(total / elapsed_days, 2),
        "budget": budget,
        "budget_remaining": round(budget - total, 2),
        "budget_percent": round(total / budget * 100, 1) if budget > 0 else 0,
    }


@app.get("/api/stats/trend")
def get_trend(month: str = ""):
    """获取当月每日支出趋势"""
    month = _normalize_month(month)
    with db() as conn:
        rows = conn.execute(
            "SELECT date, SUM(amount) as total FROM expenses WHERE date LIKE ? GROUP BY date ORDER BY date",
            (f"{month}%",),
        ).fetchall()

    # 填充整月每一天
    y, m = int(month[:4]), int(month[5:7])
    days = calendar.monthrange(y, m)[1]

    data_map = {r["date"]: round(r["total"], 2) for r in rows}
    return [
        {"date": f"{month}-{d:02d}", "amount": data_map.get(f"{month}-{d:02d}", 0)}
        for d in range(1, days + 1)
    ]


@app.get("/api/stats/by_category")
def get_by_category(month: str = ""):
    """获取当月分类支出统计"""
    month = _normalize_month(month)
    with db() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.name, c.emoji, c.color, COALESCE(SUM(e.amount), 0) as total
            FROM categories c
            LEFT JOIN expenses e ON c.id = e.category_id AND e.date LIKE ?
            GROUP BY c.id
            ORDER BY total DESC
            """,
            (f"{month}%",),
        ).fetchall()
        return [dict(r) for r in rows]


@app.get("/api/stats/heatmap")
def get_heatmap():
    """获取最近 90 天每日支出（用于热力图）"""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT date, SUM(amount) as total
            FROM expenses
            WHERE date >= date('now', '-90 days')
            GROUP BY date
            ORDER BY date
            """
        ).fetchall()
        return [{"date": r["date"], "amount": round(r["total"], 2)} for r in rows]


# ── Budget API ────────────────────────────────────────────

@app.get("/api/budgets")
def list_budgets():
    with db() as conn:
        rows = conn.execute("SELECT * FROM budgets ORDER BY month DESC").fetchall()
        return [dict(r) for r in rows]


@app.post("/api/budgets")
def set_budget(body: BudgetSet):
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO budgets (month, amount) VALUES (?, ?)",
            (body.month, body.amount),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM budgets WHERE month=?", (body.month,)).fetchone()
        return dict(row)


# ── Export API ────────────────────────────────────────────

def _csv_safe(value):
    """Prefix formula-looking cells so spreadsheets don't execute them (CSV injection)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t"):
        return "'" + value
    return value


@app.get("/api/export/csv")
def export_csv():
    """导出所有支出为 CSV（内存生成，不落盘）"""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT e.date, c.name as category, e.amount, e.note, e.created_at
            FROM expenses e
            LEFT JOIN categories c ON e.category_id = c.id
            ORDER BY e.date DESC
            """
        ).fetchall()

    output = io.StringIO()
    # UTF-8 BOM so Excel opens Chinese text correctly
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["日期", "分类", "金额", "备注", "创建时间"])
    for r in rows:
        writer.writerow([_csv_safe(v) for v in (r["date"], r["category"], r["amount"], r["note"], r["created_at"])])

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="expenses.csv"'},
    )


# ── Receipt image serving ─────────────────────────────────

@app.get("/api/receipts/{filename}")
def serve_receipt(filename: str):
    # Resolve and re-check the parent so encoded traversal (..%2F) cannot escape uploads/
    filepath = (UPLOAD_DIR / filename).resolve()
    if filepath.parent != UPLOAD_DIR.resolve() or not filepath.is_file():
        raise HTTPException(404, "Receipt not found")
    # nosniff: never let the browser reinterpret a receipt as HTML/script
    return FileResponse(filepath, headers={"X-Content-Type-Options": "nosniff"})


# ── Main ──────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765)

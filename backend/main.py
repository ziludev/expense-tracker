"""
记账网站后端 — FastAPI + SQLite + PaddleOCR
"""
import sqlite3
import os
import shutil
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "expenses.db"
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
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
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
    conn.close()


init_db()


# ── Models ────────────────────────────────────────────────

class ExpenseCreate(BaseModel):
    amount: float
    category_id: int
    date: str  # YYYY-MM-DD
    note: str = ""


class CategoryCreate(BaseModel):
    name: str
    emoji: str = "💰"
    color: str = "#6b7280"


class BudgetSet(BaseModel):
    month: str  # YYYY-MM
    amount: float


# ── Categories API ────────────────────────────────────────

@app.get("/api/categories")
def list_categories():
    conn = get_db()
    rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/categories")
def create_category(body: CategoryCreate):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO categories (name, emoji, color) VALUES (?, ?, ?)",
        (body.name, body.emoji, body.color),
    )
    conn.commit()
    cat = conn.execute("SELECT * FROM categories WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(cat)


@app.put("/api/categories/{cat_id}")
def update_category(cat_id: int, body: CategoryCreate):
    conn = get_db()
    conn.execute(
        "UPDATE categories SET name=?, emoji=?, color=? WHERE id=?",
        (body.name, body.emoji, body.color, cat_id),
    )
    conn.commit()
    cat = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
    conn.close()
    if not cat:
        raise HTTPException(404, "Category not found")
    return dict(cat)


@app.delete("/api/categories/{cat_id}")
def delete_category(cat_id: int):
    conn = get_db()
    conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── Expenses API ──────────────────────────────────────────

@app.get("/api/expenses")
def list_expenses(
    page: int = 1,
    page_size: int = 20,
    category_id: Optional[int] = None,
    keyword: str = "",
    date_from: str = "",
    date_to: str = "",
    sort: str = "date_desc",
):
    conn = get_db()
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

    # Count
    count_row = conn.execute(
        f"SELECT COUNT(*) FROM expenses e {where}", params
    ).fetchone()
    total = count_row[0]

    # Page
    offset = (page - 1) * page_size
    rows = conn.execute(
        f"""
        SELECT e.*, c.name as category_name, c.emoji as category_emoji, c.color as category_color
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        {where}
        {order}
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    ).fetchall()
    conn.close()
    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/api/expenses/{exp_id}")
def get_expense(exp_id: int):
    conn = get_db()
    row = conn.execute(
        "SELECT e.*, c.name as category_name, c.emoji as category_emoji FROM expenses e LEFT JOIN categories c ON e.category_id=c.id WHERE e.id=?",
        (exp_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Expense not found")
    return dict(row)


@app.post("/api/expenses")
def create_expense(body: ExpenseCreate):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO expenses (amount, category_id, date, note) VALUES (?, ?, ?, ?)",
        (body.amount, body.category_id, body.date, body.note),
    )
    conn.commit()
    exp = conn.execute(
        "SELECT e.*, c.name as category_name, c.emoji as category_emoji FROM expenses e LEFT JOIN categories c ON e.category_id=c.id WHERE e.id=?",
        (cur.lastrowid,),
    ).fetchone()
    conn.close()
    return dict(exp)


@app.put("/api/expenses/{exp_id}")
def update_expense(exp_id: int, body: ExpenseCreate):
    conn = get_db()
    conn.execute(
        "UPDATE expenses SET amount=?, category_id=?, date=?, note=? WHERE id=?",
        (body.amount, body.category_id, body.date, body.note, exp_id),
    )
    conn.commit()
    exp = conn.execute(
        "SELECT e.*, c.name as category_name, c.emoji as category_emoji FROM expenses e LEFT JOIN categories c ON e.category_id=c.id WHERE e.id=?",
        (exp_id,),
    ).fetchone()
    conn.close()
    if not exp:
        raise HTTPException(404, "Expense not found")
    return dict(exp)


@app.delete("/api/expenses/{exp_id}")
def delete_expense(exp_id: int):
    conn = get_db()
    # 同时删除关联的 receipt 文件
    row = conn.execute("SELECT receipt_path FROM expenses WHERE id=?", (exp_id,)).fetchone()
    if row and row["receipt_path"]:
        p = Path(row["receipt_path"])
        if p.exists():
            p.unlink()
    conn.execute("DELETE FROM expenses WHERE id=?", (exp_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ── OCR API ───────────────────────────────────────────────

@app.post("/api/ocr")
async def ocr_receipt(file: UploadFile = File(...)):
    """上传账单图片，返回 OCR 识别结果"""
    # 保存上传的文件
    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else "png"
    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}.{ext}"
    filepath = UPLOAD_DIR / filename

    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # OCR 识别
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(
            text_detection_model_name="PP-OCRv6_small_det",
            text_recognition_model_name="PP-OCRv6_small_rec",
        )
        result = ocr.predict(str(filepath))
        res = result[0]
        texts = res["rec_texts"]
        scores = [float(s) for s in res["rec_scores"]]

        # 尝试从识别结果中提取金额和日期
        lines = []
        for text, score in zip(texts, scores):
            lines.append({"text": text, "confidence": round(score, 4)})

        return {
            "success": True,
            "lines": lines,
            "receipt_path": str(filepath),
            "suggested_amount": _extract_amount(texts),
            "suggested_date": _extract_date(texts),
        }
    except Exception as e:
        return {"success": False, "error": str(e), "receipt_path": str(filepath)}


def _extract_amount(texts: list[str]) -> Optional[float]:
    """从 OCR 文本中尝试提取金额"""
    import re

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
    import re

    for text in texts:
        m = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", text)
        if m:
            return m.group(1).replace("/", "-")
    return None


# ── Stats API ─────────────────────────────────────────────

@app.get("/api/stats/summary")
def get_summary(month: str = ""):
    """获取统计摘要：当月总支出、日均、预算进度"""
    if not month:
        month = datetime.now().strftime("%Y-%m")

    conn = get_db()
    # 当月总支出
    total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE date LIKE ?",
        (f"{month}%",),
    ).fetchone()[0]

    # 当月天数
    days_in_month = 30
    try:
        y, m = int(month[:4]), int(month[5:7])
        import calendar
        days_in_month = calendar.monthrange(y, m)[1]
    except:
        pass

    # 预算
    budget_row = conn.execute(
        "SELECT amount FROM budgets WHERE month=?", (month,)
    ).fetchone()
    budget = budget_row["amount"] if budget_row else 0

    conn.close()
    return {
        "month": month,
        "total": round(total, 2),
        "daily_avg": round(total / max(1, min(date.today().day, days_in_month)), 2),
        "budget": budget,
        "budget_remaining": round(budget - total, 2),
        "budget_percent": round(total / budget * 100, 1) if budget > 0 else 0,
    }


@app.get("/api/stats/trend")
def get_trend(month: str = ""):
    """获取当月每日支出趋势"""
    if not month:
        month = datetime.now().strftime("%Y-%m")

    conn = get_db()
    rows = conn.execute(
        "SELECT date, SUM(amount) as total FROM expenses WHERE date LIKE ? GROUP BY date ORDER BY date",
        (f"{month}%",),
    ).fetchall()
    conn.close()

    # 填充整月每一天
    import calendar
    y, m = int(month[:4]), int(month[5:7])
    days = calendar.monthrange(y, m)[1]

    data_map = {r["date"]: round(r["total"], 2) for r in rows}
    result = []
    for d in range(1, days + 1):
        day_str = f"{month}-{d:02d}"
        result.append({"date": day_str, "amount": data_map.get(day_str, 0)})
    return result


@app.get("/api/stats/by_category")
def get_by_category(month: str = ""):
    """获取当月分类支出统计"""
    if not month:
        month = datetime.now().strftime("%Y-%m")

    conn = get_db()
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
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/stats/heatmap")
def get_heatmap():
    """获取最近 90 天每日支出（用于热力图）"""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT date, SUM(amount) as total
        FROM expenses
        WHERE date >= date('now', '-90 days')
        GROUP BY date
        ORDER BY date
        """
    ).fetchall()
    conn.close()
    return [{"date": r["date"], "amount": round(r["total"], 2)} for r in rows]


# ── Budget API ────────────────────────────────────────────

@app.get("/api/budgets")
def list_budgets():
    conn = get_db()
    rows = conn.execute("SELECT * FROM budgets ORDER BY month DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/budgets")
def set_budget(body: BudgetSet):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO budgets (month, amount) VALUES (?, ?)",
        (body.month, body.amount),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM budgets WHERE month=?", (body.month,)).fetchone()
    conn.close()
    return dict(row)


# ── Export API ────────────────────────────────────────────

@app.get("/api/export/csv")
def export_csv():
    """导出所有支出为 CSV"""
    conn = get_db()
    rows = conn.execute(
        """
        SELECT e.date, c.name as category, e.amount, e.note, e.created_at
        FROM expenses e
        LEFT JOIN categories c ON e.category_id = c.id
        ORDER BY e.date DESC
        """
    ).fetchall()
    conn.close()

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["日期", "分类", "金额", "备注", "创建时间"])
    for r in rows:
        writer.writerow([r["date"], r["category"], r["amount"], r["note"], r["created_at"]])

    output.seek(0)
    csv_path = BASE_DIR / "export.csv"
    csv_path.write_text(output.getvalue(), encoding="utf-8-sig")
    return FileResponse(csv_path, filename="expenses.csv", media_type="text/csv")


# ── Receipt image serving ─────────────────────────────────

@app.get("/api/receipts/{filename}")
def serve_receipt(filename: str):
    filepath = UPLOAD_DIR / filename
    if not filepath.exists():
        raise HTTPException(404, "Receipt not found")
    return FileResponse(filepath)


# ── Main ──────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765)

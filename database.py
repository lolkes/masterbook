import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", Path(__file__).with_name("masterbook.db")))
STATUSES = {"new", "progress", "done", "cancelled"}
PAYMENTS = {"unpaid", "partial", "paid"}


def get_connection():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    c.execute("PRAGMA journal_mode=WAL")
    return c


def init_db():
    with get_connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS clients(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS jobs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            client_id INTEGER,
            service TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            expenses REAL NOT NULL DEFAULT 0,
            address TEXT DEFAULT '',
            job_date TEXT DEFAULT CURRENT_DATE,
            comment TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'done',
            payment_status TEXT NOT NULL DEFAULT 'paid',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS expenses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            expense_date TEXT DEFAULT CURRENT_DATE,
            comment TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_clients_user ON clients(user_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_user_date ON jobs(user_id,job_date);
        CREATE INDEX IF NOT EXISTS idx_expenses_user_date ON expenses(user_id,expense_date);
        CREATE INDEX IF NOT EXISTS idx_jobs_client ON jobs(client_id);
        """)


def validate_client(u, cid):
    if cid is None:
        return
    with get_connection() as c:
        if not c.execute("SELECT 1 FROM clients WHERE id=? AND user_id=?", (cid, u)).fetchone():
            raise ValueError("Client does not belong to user")


def create_client(u, name, phone="", address=""):
    with get_connection() as c:
        return c.execute(
            "INSERT INTO clients(user_id,name,phone,address) VALUES(?,?,?,?)",
            (u, name.strip(), phone.strip(), address.strip()),
        ).lastrowid


def get_clients(u):
    with get_connection() as c:
        rows = c.execute("""
            SELECT c.*,
                   COUNT(CASE WHEN j.status!='cancelled' THEN j.id END) jobs_count,
                   COALESCE(SUM(CASE WHEN j.status!='cancelled' THEN j.price ELSE 0 END),0) total_income
            FROM clients c
            LEFT JOIN jobs j ON j.client_id=c.id AND j.user_id=?
            WHERE c.user_id=?
            GROUP BY c.id
            ORDER BY c.id DESC
        """, (u, u)).fetchall()
        return [dict(r) for r in rows]


def update_client(u, i, name, phone="", address=""):
    with get_connection() as c:
        c.execute("UPDATE clients SET name=?,phone=?,address=? WHERE id=? AND user_id=?", (name.strip(), phone.strip(), address.strip(), i, u))
        return c.total_changes > 0


def delete_client(u, i):
    with get_connection() as c:
        c.execute("DELETE FROM clients WHERE id=? AND user_id=?", (i, u))
        return c.total_changes > 0


def create_job(u, cid, service, price, expenses, address, date, comment, status="done", payment_status="paid"):
    with get_connection() as c:
        return c.execute("""
            INSERT INTO jobs(user_id,client_id,service,price,expenses,address,job_date,comment,status,payment_status)
            VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (u, cid, service.strip(), price, expenses, address.strip(), date, comment.strip(), status, payment_status)).lastrowid


def update_job(u, i, cid, service, price, expenses, address, date, comment, status, payment_status):
    with get_connection() as c:
        c.execute("""
            UPDATE jobs SET client_id=?,service=?,price=?,expenses=?,address=?,job_date=?,comment=?,status=?,payment_status=?
            WHERE id=? AND user_id=?
        """, (cid, service.strip(), price, expenses, address.strip(), date, comment.strip(), status, payment_status, i, u))
        return c.total_changes > 0


def delete_job(u, i):
    with get_connection() as c:
        c.execute("DELETE FROM jobs WHERE id=? AND user_id=?", (i, u))
        return c.total_changes > 0


def create_expense(u, title, amount, date, comment=""):
    with get_connection() as c:
        return c.execute("INSERT INTO expenses(user_id,title,amount,expense_date,comment) VALUES(?,?,?,?,?)", (u, title.strip(), amount, date, comment.strip())).lastrowid


def update_expense(u, i, title, amount, date, comment=""):
    with get_connection() as c:
        c.execute("UPDATE expenses SET title=?,amount=?,expense_date=?,comment=? WHERE id=? AND user_id=?", (title.strip(), amount, date, comment.strip(), i, u))
        return c.total_changes > 0


def delete_expense(u, i):
    with get_connection() as c:
        c.execute("DELETE FROM expenses WHERE id=? AND user_id=?", (i, u))
        return c.total_changes > 0


def _period_sql(period, col):
    if period == "week":
        return f" AND {col} >= date('now','-7 days')"
    if period == "month":
        return f" AND {col} >= date('now','-30 days')"
    return ""


def get_stats(u, period="all"):
    with get_connection() as c:
        wj = _period_sql(period, "job_date")
        we = _period_sql(period, "expense_date")
        income = c.execute(f"SELECT COALESCE(SUM(price),0) FROM jobs WHERE user_id=? AND status!='cancelled'{wj}", (u,)).fetchone()[0]
        job_expenses = c.execute(f"SELECT COALESCE(SUM(expenses),0) FROM jobs WHERE user_id=? AND status!='cancelled'{wj}", (u,)).fetchone()[0]
        other_expenses = c.execute(f"SELECT COALESCE(SUM(amount),0) FROM expenses WHERE user_id=?{we}", (u,)).fetchone()[0]
        jobs = c.execute(f"SELECT COUNT(*) FROM jobs WHERE user_id=?{wj}", (u,)).fetchone()[0]
        clients = c.execute("SELECT COUNT(*) FROM clients WHERE user_id=?", (u,)).fetchone()[0]
        unpaid = c.execute(f"SELECT COALESCE(SUM(price),0) FROM jobs WHERE user_id=? AND status!='cancelled' AND payment_status!='paid'{wj}", (u,)).fetchone()[0]
        return {"income": income, "expenses": job_expenses + other_expenses, "profit": income - job_expenses - other_expenses, "clients": clients, "jobs": jobs, "unpaid": unpaid}


def get_summary(u):
    with get_connection() as c:
        rows = c.execute("""
            SELECT substr(job_date,1,7) month,
                   COALESCE(SUM(CASE WHEN status!='cancelled' THEN price ELSE 0 END),0) income,
                   COALESCE(SUM(CASE WHEN status!='cancelled' THEN expenses ELSE 0 END),0) expenses
            FROM jobs WHERE user_id=? GROUP BY substr(job_date,1,7) ORDER BY month DESC LIMIT 6
        """, (u,)).fetchall()
        return [dict(r) for r in rows][::-1]


def get_jobs(u, limit=100):
    with get_connection() as c:
        rows = c.execute("""
            SELECT jobs.*,clients.name client_name
            FROM jobs
            LEFT JOIN clients ON clients.id=jobs.client_id AND clients.user_id=jobs.user_id
            WHERE jobs.user_id=?
            ORDER BY jobs.job_date DESC,jobs.id DESC LIMIT ?
        """, (u, limit)).fetchall()
        return [dict(r) for r in rows]


def get_expenses(u, limit=100):
    with get_connection() as c:
        return [dict(r) for r in c.execute("SELECT * FROM expenses WHERE user_id=? ORDER BY expense_date DESC,id DESC LIMIT ?", (u, limit)).fetchall()]


def get_backup(u):
    return {"version": "8.0", "clients": get_clients(u), "jobs": get_jobs(u, 5000), "expenses": get_expenses(u, 5000)}

import sqlite3
from pathlib import Path
DB_PATH=Path(__file__).with_name('masterbook.db')
def get_connection():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c
def init_db():
    with get_connection() as c: c.executescript('''CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT DEFAULT '',address TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY AUTOINCREMENT,client_id INTEGER,service TEXT NOT NULL,price REAL NOT NULL DEFAULT 0,expenses REAL NOT NULL DEFAULT 0,address TEXT DEFAULT '',job_date TEXT DEFAULT CURRENT_DATE,comment TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(client_id) REFERENCES clients(id) ON DELETE SET NULL);CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,amount REAL NOT NULL DEFAULT 0,expense_date TEXT DEFAULT CURRENT_DATE,comment TEXT DEFAULT '',created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
def create_client(name,phone='',address=''):
    with get_connection() as c:return c.execute('INSERT INTO clients(name,phone,address) VALUES(?,?,?)',(name.strip(),phone.strip(),address.strip())).lastrowid
def get_clients():
    with get_connection() as c:return [dict(x) for x in c.execute('SELECT * FROM clients ORDER BY id DESC')]
def create_job(client_id,service,price,expenses,address,job_date,comment):
    with get_connection() as c:c.execute('INSERT INTO jobs(client_id,service,price,expenses,address,job_date,comment) VALUES(?,?,?,?,?,?,?)',(client_id,service,price,expenses,address,job_date,comment))
def create_expense(title,amount,expense_date,comment=''):
    with get_connection() as c:c.execute('INSERT INTO expenses(title,amount,expense_date,comment) VALUES(?,?,?,?)',(title,amount,expense_date,comment))
def get_stats():
    with get_connection() as c:
        income=c.execute('SELECT COALESCE(SUM(price),0) FROM jobs').fetchone()[0]; je=c.execute('SELECT COALESCE(SUM(expenses),0) FROM jobs').fetchone()[0]; oe=c.execute('SELECT COALESCE(SUM(amount),0) FROM expenses').fetchone()[0]; clients=c.execute('SELECT COUNT(*) FROM clients').fetchone()[0]; jobs=c.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
        return {'income':income,'expenses':je+oe,'profit':income-je-oe,'clients':clients,'jobs':jobs}
def get_jobs(limit=50):
    with get_connection() as c:return [dict(x) for x in c.execute('SELECT jobs.*,clients.name client_name FROM jobs LEFT JOIN clients ON clients.id=jobs.client_id ORDER BY jobs.id DESC LIMIT ?',(limit,))]

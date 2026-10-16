import os
import pymysql
import sqlite3
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "")
DB_USER = os.getenv("DB_USER", "u373142447_snacks")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "u373142447_friday")
DB_PORT = int(os.getenv("DB_PORT", "3306"))

EMPLOYEES_LIST = [
    'Faiyas', 'Abdul', 'Abhinand', 'Ajay', 'Akash', 'Basha', 'Namratha', 'Deepthi',
    'Fayeem', 'Arun', 'Bhagyaraj', 'Sanket', 'Vijey', 'Jose', 'Ajayan', 'Disha',
    'Aneesh', 'Srinivasa', 'Jerald', 'Mani', 'Arya', 'Dayananda', 'Karthik', 'Lokesh',
    'Manjunath', 'Nithish', 'Pachiyappan', 'Praveen', 'Rudresh', 'Sridhar', 'Sunil', 'Tejas',
    'Vinay', 'Sangeetha', 'Sanjay', 'Sudhanva', 'Supreeth', 'Manikandan', 'Poorvi', 'Sunil K',
    'Sahithi', 'Sirisha', 'Alan', 'Deepak', 'Sajith', 'Sneha', 'Ezhilarasu', 'Pattan'
]

def is_mysql():
    return bool(DB_HOST and DB_PASSWORD)

def get_connection():
    if is_mysql():
        return pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
    else:
        # Fallback to local SQLite if MySQL credentials not set yet
        conn = sqlite3.connect("zentegra_snacks.db")
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    if is_mysql():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                `key` VARCHAR(100) PRIMARY KEY,
                `value` TEXT NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(150) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friday_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_date DATE UNIQUE NOT NULL,
                allowance_amount DECIMAL(10,2) DEFAULT 100.00,
                status VARCHAR(20) DEFAULT 'open',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_ref VARCHAR(50) UNIQUE NOT NULL,
                session_id INT NOT NULL,
                employee_id INT NOT NULL,
                food_amount DECIMAL(10,2) NOT NULL,
                company_pays DECIMAL(10,2) NOT NULL,
                employee_pays DECIMAL(10,2) NOT NULL,
                payment_mode VARCHAR(20) DEFAULT 'NONE',
                payment_status VARCHAR(50) NOT NULL,
                upi_reference VARCHAR(100) NULL,
                paid_at DATETIME NULL,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_session_emp (session_id, employee_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendor_expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id INT NULL,
                session_date DATE NOT NULL,
                vendor_name VARCHAR(200) NOT NULL,
                invoice_amount DECIMAL(10,2) NOT NULL,
                amount_paid DECIMAL(10,2) NOT NULL,
                payment_date DATE NULL,
                payment_reference VARCHAR(100) NULL,
                notes TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                order_id INT NULL,
                action VARCHAR(100) NOT NULL,
                performed_by VARCHAR(100) NOT NULL,
                details TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

        # Default Settings
        settings = [
            ('upi_id', '9663287777@ybl'),
            ('upi_name', 'Zentegra Friday Snacks'),
            ('allowance_amount', '100'),
            ('admin_pin', 'admin123')
        ]
        for k, v in settings:
            cursor.execute("INSERT IGNORE INTO app_settings (`key`, `value`) VALUES (%s, %s)", (k, v))

        # Seed 48 Employees
        for name in EMPLOYEES_LIST:
            cursor.execute("INSERT IGNORE INTO employees (name) VALUES (%s)", (name,))

    else:
        # SQLite dialect
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TEXT DEFAULT (datetime('now', '+05:30'))
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friday_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_date TEXT UNIQUE NOT NULL,
                allowance_amount REAL DEFAULT 100,
                status TEXT DEFAULT 'open',
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now', '+05:30'))
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_ref TEXT UNIQUE NOT NULL,
                session_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                food_amount REAL NOT NULL,
                company_pays REAL NOT NULL,
                employee_pays REAL NOT NULL,
                payment_mode TEXT DEFAULT 'NONE',
                payment_status TEXT NOT NULL,
                upi_reference TEXT,
                paid_at TEXT,
                submitted_at TEXT DEFAULT (datetime('now', '+05:30')),
                updated_at TEXT DEFAULT (datetime('now', '+05:30')),
                UNIQUE(session_id, employee_id)
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendor_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                session_date TEXT NOT NULL,
                vendor_name TEXT NOT NULL,
                invoice_amount REAL NOT NULL,
                amount_paid REAL NOT NULL,
                payment_date TEXT,
                payment_reference TEXT,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now', '+05:30'))
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                action TEXT NOT NULL,
                performed_by TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now', '+05:30'))
            );
        """)

        settings = [
            ('upi_id', '9663287777@ybl'),
            ('upi_name', 'Zentegra Friday Snacks'),
            ('allowance_amount', '100'),
            ('admin_pin', 'admin123')
        ]
        for k, v in settings:
            cursor.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (k, v))

        for name in EMPLOYEES_LIST:
            cursor.execute("INSERT OR IGNORE INTO employees (name) VALUES (?)", (name,))

        conn.commit()

    conn.close()

def get_friday_date():
    today = date.today()
    # Friday is 4 (Monday=0 ... Friday=4, Saturday=5, Sunday=6)
    diff = 4 - today.weekday()
    target_friday = today + timedelta(days=diff)
    return target_friday.strftime("%Y-%m-%d")
